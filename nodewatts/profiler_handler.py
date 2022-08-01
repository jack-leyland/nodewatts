
from nodewatts.config import NWConfig
from nodewatts.subprocess_manager import NWSubprocessError, NWSubprocessTimeout, SubprocessManager
from nodewatts.error import NodewattsError

import os
import shutil
import json
import logging
from datetime import datetime
import time
import subprocess
import pwd
logger = logging.getLogger("Main")

# Note:
# Must force user to ensure correct version of node is the default,
# If the the project requires an older version, supply and nvm exec command
# and ensure bash recognizes it.

class ProfilerException(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class ProfilerInitError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class ProfilerHandler():
    def __init__(self, conf: NWConfig, manager: SubprocessManager):
        self.root = conf.root_path
        self.entry_path = os.path.join(conf.root_path, conf.entry_file)
        self.entry_name = conf.entry_file
        self.commands = conf.commands
        self.profile_title = datetime.now().isoformat()
        self.tmp_path = conf.tmp_path
        self.socket_port = conf.profiler_port
        self.proc_manager = manager
        self.profiler_env_vars = {}
        self.es6 = conf.es6
        self.server_process = None
        self.test_runner_timeout = conf.test_runner_timeout
        self.deps_installed = False
        self.fail_code = None
        self.aliased_npm_requirements = [
            "nw-zeromq@npm:zeromq@6.0.0-beta.6", "nw-prof@npm:v8-profiler-next"]
        self._db_service_index_path = os.path.join(
            os.getcwd(), "scripts/nodewatts_cpu_profile_db/src/main/index.js")
        self._profiler_scripts_root = os.path.join(
            os.getcwd(), "scripts/nodewatts_profiler_agent")
        self.server_wait = conf.server_startup_wait
        self.aliased_npm_requirements = [
            "nw-zeromq@npm:zeromq@6.0.0-beta.6", "nw-prof@npm:v8-profiler-next"]

        self.profiler_env_vars["PATH_TO_DB_SERVICE"] = self._db_service_index_path
        self.profiler_env_vars["PROFILE_TITLE"] = self.profile_title
        self.profiler_env_vars["TEST_SOCKET_PORT"] = str(self.socket_port)
        self.profiler_env_vars["NODEWATTS_TMP_PATH"] = self.tmp_path
        self.profiler_env_vars["TESTCMD"] = self.commands["runTests"]
        self.profiler_env_vars["ZMQ_INSTALLED_PATH"] = os.path.join(
            self.root, "node_modules/nw-zeromq")
        if conf.engine_conf_args["internal_db_uri"][-1] == "/":
            self.profiler_env_vars["NODEWATTS_DB_URI"] = conf.engine_conf_args["internal_db_uri"] + "nodewatts"
        else:
            self.profiler_env_vars["NODEWATTS_DB_URI"] = conf.engine_conf_args["internal_db_uri"] + "/nodewatts"

        if conf.use_nvm:
            if not conf.override_nvm_path:
                try:
                    self.nvm_path = self._resolve_nvm_path(conf.user, conf.node_version)
                except NodewattsError as e :
                    logger.error(str(e))
                    raise ProfilerInitError(None) from None
            else:
                self.nvm_path = conf.override_nvm_path
        else: 
            self.nvm_path = None

        self._save_copy_of_entry_file()
        self._inject_profiler_script()
        self._install_npm_dependencies()

    # Starts the web server process. Performs necessary cleanup and exits pacakge in case of 
    # failure. Safe to call directly. Return the PID of the server if successful
    def start_server(self) -> int:
        logger.debug("Starting cpu profiler.")
        self.server_process = self.proc_manager.project_process_async(
                "echo \"Running server with node version: $(which node)\" && "
                + self.commands["serverStart"], custom_env=self.profiler_env_vars, 
                inject_to_path=self.nvm_path)
        # Poll the server process in 1 second increments for the specified wait duration.
        # If the PID file isn't there after the wait time, we assume it hasn't started correctly.
        # However, cases remain where there server takes a long time to start up
        # and may report the PID before a fatal crash.
        # To handle these cases, the server process will be repeatedly polled
        # throughout the operations that follow its startup in order to catch these
        # cases and report crash info to the user.
        # Note that PID file is used since node is run as a child of shell the shell process
        # so we do not want to include the shell in the monitoring
        attempts = 0
        while True:
            retcode = self.server_process.poll()
            if retcode is None:
                if os.path.exists(os.path.join(os.getcwd(), "tmp/PID.txt")):
                    logger.debug(
                        "PID file located on attempt " + str(attempts+1)+". Proceeding.")
                    break
            else:
                logger.error("Web server did not start successfully. Exited with return code: " +
                                str(self.server_process.returncode))
                raise ProfilerException(None)
            attempts += 1
            if attempts == self.server_wait:
                logger.error("Failed to locate server PID in " + str(attempts) + " attempts. This could be an indication " +
                             "that the given web server took longer than "+str(self.server_wait)+" seconds to start, " +
                             "or that it prematurely exited with a return code of 0.")
                logger.info("To allow the server greater time to initilize, set \"dev-serverWait\" config " +
                            "option in the config file to the desired wait time in seconds.")
                raise ProfilerException(None)
            time.sleep(1.0)
        logger.debug("Server started successfully")
        with open(os.path.join(self.tmp_path, "PID.txt")) as f:
            pid = f.read()
        return pid

    # Polls server process to ensure it is still alive. None means alive, otherwise it will return a retcode
    def poll_server(self) -> int | None:
        return self.server_process.poll()

    # Runs provided test suite or cleans up and exits in case of failure
    def run_test_suite(self) -> None:
        logger.info("Running tests. This may take a moment.")
        cmd = "node " + \
            os.path.join(self._profiler_scripts_root, "test-runner.js")
        if self.server_process.poll() is None:
            try:
                stdout, stderr = self.proc_manager.project_process_blocking(
                    cmd, custom_env=self.profiler_env_vars, timeout=self.test_runner_timeout, inject_to_path=self.nvm_path)
                logger.debug("Test Suite run successfully: \n" +
                             "stdout: \n" + stdout + "stderr: \n" + stderr)
            except NWSubprocessError as e:
                logger.error("Failed to run test suite. Error: \n" + str(e))
                raise ProfilerException(None)
            except NWSubprocessTimeout as e:
                logger.error("Test suite process timeout out in " + str(self.test_runner_timeout) +
                             " seconds." + "If you believe the provided test suite requires longer than this" +
                             " to sucessfully complete, please configure the \"dev-testRunnerTimeout\" " +
                             "setting in the config file as necessary. \n" + "Test runner output before timeout: \n" + str(e))
                raise ProfilerException(None)
        else:
            logger.error("Web server encounted an error. Exited with return code: " +
                            str(self.server_process.returncode))
            raise ProfilerException(None)

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
            logger.error("Could not locate nvm path for specified version. Tried: " + nvm_path)
            raise ProfilerException(None)
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
        logger.info("Installing npm dependencies. This may take a moment.")
        cmd = "npm i -D " + \
            " ".join(self.aliased_npm_requirements)
        try:
            stdout, stderr = self.proc_manager.project_process_blocking(cmd, inject_to_path=self.nvm_path)
        except NWSubprocessError as e:
            logger.error("Failed to install npm dependencies. Error:" + str(e))
            raise ProfilerInitError(None)
        logger.debug("Dependencies installed successfully. stdout: \n" + stdout + "\n"
                     + "stderr: \n" + stderr)
        self.deps_installed = True

    def _uninstall_npm_dependencies(self) -> None:
        logger.info("Uninstalling npm dependencies. This may take a moment.")
        aliases = ["nw-zeromq", "nw-prof"]
        uninstall = "npm uninstall " + " ".join(aliases)
        try:
            stdout, stderr = self.proc_manager.project_process_blocking(
                    uninstall, inject_to_path=self.nvm_path)
        except NWSubprocessError as e:
            logger.warning("Failed to uninstall the following temporary aliased npm packages: "
                            + " ".join(self.aliased_npm_requirements)
                            + ". These package will need to removed manually. NPM error message: \n"
                            + str(e))
        else: 
            logger.debug("Dependencies uninstalled successfully. stdout: \n" + stdout + "\n"
                        + "stderr: \n" + stderr)
            self.deps_installed = False

    def _is_es6(self) -> bool:
        package = self._load_package_file()
        if "type" in package and package["type"] == "module":
            self.es6 = True
        return self.es6

    def _load_package_file(self) -> dict:
        pkg_path = os.path.join(self.root, "package.json")
        if not os.path.exists(pkg_path):
            raise ProfilerException("Project must include a package.json file.")
        with open(pkg_path, "r") as f:
            package = json.load(f)
        return package

    def _log_server_output(self) -> None:
        try:
            output, _ = self.server_process.communicate(timeout=5)
            logger.debug("Server output: \n" + output)
        except subprocess.TimeoutExpired:
            logger.debug("Unable to terminate server process and retrieve output. " + 
            "Please ensure server exited successfully before runnging nodewatts again")

    def _shutdown_server(self) -> None:
        logger.debug("Shutting down server.")
        self.proc_manager.terminate_process_tree(self.server_process.pid)
        self._log_server_output()

    def cleanup(self) -> None:
        logger.debug("Cleaning up project directory.")
        self._restore_entry_file()
        if self.deps_installed:
            self._uninstall_npm_dependencies()
        if self.server_process is not None:
            if self.server_process.poll() is None:
                self._shutdown_server()
            else:
                logger.debug("Unexpected server exit with return code: " + str(self.server_process.poll()))
                self._log_server_output()
                self.fail_code = self.server_process.poll()

            