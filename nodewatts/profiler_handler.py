import os
from .config import NWConfig
from .subprocess_manager import NWSubprocessError, NWSubprocessTimeout, SubprocessManager
from .error import NodewattsError
import shutil
import json
import logging
from datetime import datetime
import time
import sys
import subprocess
import pwd
from psutil import Process
logger = logging.getLogger("Main")

# Note:
# Must force user to ensure correct version of node is the default,
# If the the project requires an older version, supply and nvm exec command
# and ensure bash recognizes it.


class ProfilerHandler:
    def __init__(self, conf: NWConfig, manager: SubprocessManager):
        self.root = conf.root_path
        self.entry_path = os.path.join(conf.root_path, conf.entry_file)
        self.entry_name = conf.entry_file
        self.commands = conf.commands
        self.tmp_path = conf.tmp_path
        self.socket_port = conf.profiler_port
        self.proc_manager = manager
        self.profiler_env_vars = {}
        self.server_process = None
        self.test_runner_timeout = conf.test_runner_timeout
        self.aliased_npm_requirements = [
            "nw-zeromq@npm:zeromq@6.0.0-beta.6", "nw-prof@npm:v8-profiler-next"]
        self._db_service_index_path = os.path.join(
            os.getcwd(), "modules/nodewatts_cpu_profile_db/src/main/index.js")
        self._profiler_scripts_root = os.path.join(
            os.getcwd(), "modules/nodewatts_profiler_agent/src")
        self.server_wait = conf.server_startup_wait

        self.profiler_env_vars["PATH_TO_DB_SERVICE"] = self._db_service_index_path
        self.profiler_env_vars["PROFILE_TITLE"] = datetime.now().isoformat()
        self.profiler_env_vars["TEST_SOCKET_PORT"] = str(self.socket_port)
        self.profiler_env_vars["NODEWATTS_TMP_PATH"] = self.tmp_path
        self.profiler_env_vars["TESTCMD"] = self.commands["runTests"]
        self.profiler_env_vars["ZMQ_INSTALLED_PATH"] = os.path.join(
            self.root, "node_modules/nw-zeromq")
        self.profiler_env_vars["NODEWATTS_DB_URI"] = conf.engine_conf_args["internal_db_uri"]

        if conf.use_nvm:
            try:
                self.nvm_path = self._resolve_nvm_path(conf.user, conf.node_version)
            except NodewattsError as e :
                logger.error(str(e))
                sys.exit(1)
        else: 
            self.nvm_path = None

        self._save_copy_of_entry_file()
        self._inject_profiler_script()
        self._install_npm_dependencies()

    # Starts the web server process. Performs necessary cleanup and exits pacakge in case of 
    # failure. Safe to call directly
    def start_server(self) -> None:
        logger.debug("Starting cpu profiler.")
        self.server_process = self.proc_manager.project_process_async(
            "echo \"Running server with node version: $(which node)\" && "
            + self.commands["serverStart"], custom_env=self.profiler_env_vars)
        # Poll the server process in 1 second increments for the specified wait duration.
        # If the PID file isn't there after the wait time, we assume it hasn't started correctly.
        # However, cases remain where there server takes a long time to start up
        # and may report the PID before a fatal crash.
        # To handle these cases, the server process will be repeatedly polled
        # throughout the operations that follow its startup in order to catch these
        # cases and report crash info to the user.
        attempts = 0
        while True:
            retcode = self.server_process.poll()
            if retcode is None:
                if os.path.exists(os.path.join(os.getcwd(), "tmp/PID.txt")):
                    logger.debug(
                        "PID file located on attempt " + str(attempts+1)+". Proceeding.")
                    break
            else:
                self.handle_server_fail()
            attempts += 1
            if attempts == self.server_wait:
                logger.error("Failed to locate server PID in " + str(attempts) + " attempts. This could be an indication " +
                             "that the given web server took longer than "+str(self.server_wait)+" seconds to start, " +
                             "or that it prematurely exited with a return code of 0.")
                logger.info("To allow the server greater time to initilize, set \"dev-serverWait\" config " +
                            "option in the config file to the desired wait time in seconds.")
                self.cleanup(uninstall_deps=True)
                sys.exit(-2)
            time.sleep(1.0)
        logger.debug("Server started successfully")

    # Polls server process to ensure it is still alive. None means alive, otherwise it will return a retcode
    def poll_server(self) -> int | None:
        return self.server_process.poll()

    # Runs provided test suite or cleans up and exits in case of failure
    def run_test_suite(self) -> None:
        logger.debug("Running provided test suite")
        cmd = "exec node " + \
            os.path.join(self._profiler_scripts_root, "test-runner.js")
        if self.server_process.poll() is None:
            try:
                stdout, stderr = self.proc_manager.project_process_blocking(
                    cmd, custom_env=self.profiler_env_vars, timeout=self.test_runner_timeout)
                logger.debug("Test Suite run successfully: \n" +
                             "stdout: \n" + stdout + "stderr: \n" + stderr)
            except NWSubprocessError as e:
                logger.error("Failed to run test suite. Error: \n" + str(e))
                self.cleanup(uninstall_deps=True, terminate_server=True)
                sys.exit(-2)
            except NWSubprocessTimeout as e:
                logger.error("Test suite process timeout out in " + str(self.test_runner_timeout) +
                             " seconds." + "If you believe the provided test suite requires longer than this" +
                             " to sucessfully complete, please configure the \"dev-testRunnerTimeout\" " +
                             "setting in the config file as necessary. \n" + "Test runner output before timeout: \n" + str(e))
                self.cleanup(uninstall_deps=True, terminate_server=True)
                sys.exit(-2)
        else:
            self.handle_server_fail()

    def _inject_profiler_script(self, ES6=False) -> None:
        if self._is_es6():
            with open(os.path.join(self._profiler_scripts_root, "es6-imports.js")) as f:
                imports = f.read()
        else:
            with open(os.path.join(self._profiler_scripts_root, "imports.js")) as f:
                imports = f.read()

        with open(self.entry_path, "r+") as f:
            content = f.read()
            f.seek(0, 0)
            f.write(imports.rstrip('\r\n') + '\n' + content)

        with open(os.path.join(self._profiler_scripts_root, "profiler-socket.js")) as f:
            script = f.read()

        with open(self.entry_path, "a+") as f:
            f.write(script)

    @staticmethod
    def _resolve_nvm_path(username:str, version:str) -> str:
        pw_record = pwd.getpwnam(username)
        homedir = pw_record.pw_dir
        nvm_path = os.path.join(homedir,".nvm" ,"versions","node","v"+version , "bin")
        if not os.path.exists(nvm_path):
            raise NodewattsError("Could not locate nvm path for specified version. Tried: " + nvm_path)
        return nvm_path

    def _save_copy_of_entry_file(self) -> None:
        shutil.copy2(self.entry_path, self.tmp_path)

    def _restore_entry_file(self) -> None:
        os.remove(self.entry_path)
        shutil.move(os.path.join(
            self.tmp_path, self.entry_name), self.entry_path)

    # Installs required package versions that are aliased to avoid collisions if
    # user is already making use of the packages in the project
    def _install_npm_dependencies(self) -> None:
        logger.debug("Installing npm dependencies...")
        cmd = "npm i -D " + \
            " ".join(self.aliased_npm_requirements)
        try:
            if self.nvm_path is None:
                stdout, stderr = self.proc_manager.project_process_blocking(cmd)
            else:
                stdout, stderr = self.proc_manager.project_process_blocking(cmd, inject_to_path=self.nvm_path)
        except NWSubprocessError as e:
            logger.error("Failed to install npm dependencies. Error:" + str(e))
            logger.debug("Cleaning up and exiting...")
            self.cleanup(uninstall_deps=False)
            sys.exit(-1)
        logger.debug("Dependencies installed successfully. stdout: \n" + stdout + "\n"
                     + "stderr: \n" + stderr)

    def _uninstall_npm_dependencies(self) -> None:
        logger.debug("Uninstalling npm dependencies...")
        aliases = ["nw-zeromq", "nw-prof"]
        uninstall = "npm uninstall " + " ".join(aliases)
        try:
            if self.nvm_path is None:
                stdout, stderr = self.proc_manager.project_process_blocking(
                    uninstall)
            else:
                stdout, stderr = self.proc_manager.project_process_blocking(
                    uninstall, inject_to_path=self.nvm_path)
        except NWSubprocessError as e:
            logger.warning("Failed to uninstall the following temporary aliased npm packages: "
                            + " ".join(self.aliased_npm_requirements)
                            + ". These package will need to removed manually. NPM error message: \n"
                            + str(e))
            logger.info("Proceeding with profile...")
        else: 
            logger.debug("Dependencies uninstalled successfully. stdout: \n" + stdout + "\n"
                        + "stderr: \n" + stderr)

    def _is_es6(self) -> bool:
        package = self._load_package_file()
        return "type" in package and package["type"] == "module"

    def _load_package_file(self) -> dict:
        pkg_path = os.path.join(self.root, "package.json")
        if not os.path.exists(pkg_path):
            raise NodewattsError("Project must include a package.json file.")
        with open(pkg_path, "r") as f:
            package = json.load(f)
        return package

    def _shutdown_server(self) -> None:
        logger.debug("Shutting down server.")
        pid = self.server_process.pid
        parent = Process(pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        try:
            output, _ = self.server_process.communicate(timeout=5)
            logger.debug("Server subprocess terminated.")
            logger.debug("Server output: \n" + output)
        except subprocess.TimeoutExpired:
            logger.debug("Unable to terminate server process and retrieve output. " + 
            "Please ensure server exited successfully before runnging nodewatts again")
    
    # Handles a server failure. Call if poll fails to perform cleanup  
    def handle_server_fail(self, on_start=False) -> None:
        if on_start:
            logger.error(
                "Web server did not start successfully. Exited with return code: " +
                str(self.server_process.returncode))
        else:
            logger.error(
                "Web server encounted an error. Exited with return code: " +
                str(self.server_process.returncode))
        try:
            output, _ = self.server_process.communicate(timeout=0.3)
            logger.debug("Server output: \n" + output)
        except Exception:
            logger.debug("Could not get output from failed server process.")
        self.cleanup(uninstall_deps=True, terminate_server=False)
        sys.exit(1)

    def cleanup(self, uninstall_deps=True, terminate_server=False) -> None:
        logger.debug("Cleaning up project directory.")
        self._restore_entry_file()
        if uninstall_deps:
            self._uninstall_npm_dependencies()
        if terminate_server:
            self._shutdown_server()
