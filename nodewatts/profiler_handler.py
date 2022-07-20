import os
from .config import NWConfig
from .subprocess_manager import NWSubprocessError, SubprocessManager
from .error import NodewattsError
import shutil
import json
import logging
from datetime import datetime
import time
import sys
import subprocess
import signal
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
        self.profiler_env = os.environ.copy()
        self.server_process = None
        self.aliased_npm_requirements = [
            "nw-zeromq@npm:zeromq@6.0.0-beta.6", "nw-prof@npm:v8-profiler-next"]
        self._db_service_index_path = os.path.join(
            os.getcwd(), "modules/nodewatts_cpu_profile_db/src/main/index.js")
        self._profiler_scripts_root = os.path.join(
            os.getcwd(), "modules/nodewatts_profiler_agent/src")
        self.server_wait = conf.server_startup_wait

        self._save_copy_of_entry_file()
        self._inject_profiler_script()
        self._install_npm_dependencies()

        self.profiler_env["PATH_TO_DB_SERVICE"] = self._db_service_index_path
        self.profiler_env["PROFILE_TITLE"] = datetime.now().isoformat()
        self.profiler_env["TEST_SOCKET_PORT"] = str(self.socket_port)
        self.profiler_env["NODEWATTS_TMP_PATH"] = self.tmp_path
        self.profiler_env["TESTCMD"] = self.commands["runTests"]

    def run_profiler(self) -> None:
        logger.debug("Starting cpu profiler.")
        self.server_process = self.proc_manager.project_process_async(
            self.commands["serverStart"], custom_env=self.profiler_env)

        # Poll the server process. If no returncode, we can check for presence of the PID file
        # as an indication the startup has been successful. We will check three times before polling for
        # a return code again.
        retcode = self.server_process.poll()
        if retcode is None:
            tries = 0
            found = False
            while True:
                if os.path.exists(os.path.join(os.getcwd(), "tmp/PID.txt")):
                    logger.debug(
                        "PID file located on first attempt. Proceeding.")
                    found = True
                    break
                tries += 1
                if tries == 3:
                    break
                time.sleep(1.0)
        else:
            self._handle_server_fail()
        if found:
            logger.debug("This would be next step. Cleaning up.")
            self.cleanup(uninstall_deps=True, terminate_server=True)
        else:
            # Second and third attempts
            retcode = self.server_process.poll()
            if retcode is None:
                if os.path.exists(os.path.join(os.getcwd(), "tmp/PID.txt")):
                    logger.debug(
                        "PID file located on second attempt. Proceeding.")
                else:
                    logger.debug(
                        "Server process running, unable to locate PID file. Waiting a further 3 seconds.")
                    time.sleep(self.server_wait)
                    if os.path.exists(os.path.join(os.getcwd(), "tmp/PID.txt")):
                        logger.debug(
                            "PID file located on final attempt. Proceeding.")
                    else:
                        logger.error("Failed to locate server PID on three attempts. This could be an indication \
                                    that the given web server took longer than 4.5 seconds to start, or that it prematurely exited \
                                    with a return code of 0.")
                        logger.info("To allow the server greater time to initilize, set \"dev-serverWait\" config \
                            option in the config file to the desired wait time in seconds.")
                        self.cleanup(uninstall_deps=True)
                        sys.exit(-2)
            else:
                self._handle_server_fail()

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

    def _save_copy_of_entry_file(self) -> None:
        shutil.copy2(self.entry_path, self.tmp_path)

    def _restore_entry_file(self) -> None:
        os.remove(self.entry_path)
        shutil.move(os.path.join(
            self.tmp_path, self.entry_name), self.entry_path)

    # installs required package versions that are aliased to avoid collisions if
    # user is already making use of the packages in the project
    def _install_npm_dependencies(self) -> None:
        logger.debug("Installing npm dependencies...")
        cmd = "npm i -D " + \
            " ".join(self.aliased_npm_requirements)
        try:
            stdout, stderr = self.proc_manager.project_process_blocking(cmd)
        except NWSubprocessError as e:
            logger.error("Failed to install npm dependencies. Error:" + str(e))
            logger.debug("Cleaning up and exiting...")
            self.cleanup(uninstall_deps=False)
            sys.exit(-1)
        logger.debug("Dependencies installed successfully. stdout: \n" + stdout + "\n"
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
        self.server_process.terminate()
        try:
            output, _ = self.server_process.communicate(timeout=1)
            logger.debug("Server terminated with return code: " +
                         str(self.server_process.returncode))
            logger.debug("Server output: \n" + output)
        except subprocess.TimeoutExpired:
            logger.debug("Server did not terminate in time. Sending SIGKILL")
            self.server_process.send_signal(signal.SIGKILL)
        logger.debug("Server shut down success.")

    def _handle_server_fail(self) -> None:
        logger.error(
            "Web server did not start successfully. Exited with return code: " +
            str(self.server_process.returncode))
        try:
            output, _ = self.server_process.communicate(timeout=0.3)
            logger.debug("Server output: \n" + output)
        except Exception:
            logger.debug("Could not get output from failed server process.")

        self.cleanup(uninstall_deps=True, terminate_server=True)
        sys.exit(-2)

    def cleanup(self, uninstall_deps=True, terminate_server=False) -> None:
        logger.debug("Cleaning up project directory.")
        self._restore_entry_file()
        if uninstall_deps:
            aliases = ["nw-zeromq", "nw-prof"]
            uninstall = "npm uninstall " + \
                " ".join(aliases)
            try:
                stdout, stderr = self.proc_manager.project_process_blocking(
                    uninstall)
            except NWSubprocessError as e:
                logger.warning("Failed to uninstall the following temporary aliased npm packages: "
                               + " ".join(self.aliased_npm_requirements)
                               + ". These package will need to removed manually. NPM error message: \n"
                               + str(e))
                logger.info("Proceeding with profile...")
            logger.debug("Dependencies uninstalled successfully. stdout: \n" + stdout + "\n"
                         + "stderr: \n" + stderr)
        if terminate_server:
            self._shutdown_server()
