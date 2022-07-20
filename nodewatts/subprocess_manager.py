import time
import os
import subprocess
import sys
import logging
from typing import Tuple, IO
from .error import NodewattsError
from .config import NWConfig
logger = logging.getLogger("Main")


class NWSubprocessError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWSubprocessTimeout(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class Singleton(object):
    def __new__(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it

    def init(self, *args, **kwds):
        pass


class SubprocessManager(Singleton):
    def __init__(self, conf: NWConfig):
        self.project_root = conf.root_path
        self.nodewatts_root = os.getcwd()
        self.entry_path = os.path.join(conf.root_path, conf.entry_file)
        logger.debug("Process manager started.")
        self.shell = conf.subprocess_shell_path

    # Execute a blocking commmand in the target Node project's root directory.
    # Raises SubprocessError if non zero return code, otherwise returns output of process
    # Used mainly for handling npm dependecies required by the tool
    def project_process_blocking(self, cmd: str, custom_env=None, timeout=None) -> Tuple[str, str]:
        try:
            if custom_env:
                proc = subprocess.run(cmd, shell=True, capture_output=True, check=True,
                                      cwd=self.project_root, text=True, executable=self.shell, env=custom_env, timeout=timeout)
            else:
                proc = subprocess.run(cmd, shell=True, capture_output=True, check=True,
                                      cwd=self.project_root, text=True, executable=self.shell, timeout=timeout)
        except subprocess.CalledProcessError as e:
            out = ("" if e.stdout is None else e.stdout)
            err = ("" if e.stderr is None else e.stderr)
            raise NWSubprocessError("Command: " + cmd + " failed with exit code " + str(e.returncode)
                                    + " \nstdout dump: \n" + out + " \n stderr dump: \n" + err) from None
        except subprocess.TimeoutExpired as e:
            out = ("" if e.stdout is None else e.stdout.decode('utf-8'))
            err = ("" if e.stderr is None else e.stderr.decode('utf-8'))
            raise NWSubprocessTimeout(
                "stdout dump: \n" + out + " \n stderr dump: \n" + err) from None
        else:
            return (proc.stdout, proc.stderr)

    # Executes a command asynchronously from project root dir
    # such that it will not block the spawning of further subprocesses.
    # Used mainly to run the web server during profiling.
    # Unlike the blocking methods, aync process spawn methods will return the
    # process instance such that the caller can verify it is still alive before
    # running others jobs that depend on it.

    def project_process_async(self, cmd: str, custom_env=None) -> IO:

        if custom_env:
            return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=custom_env,
                                    cwd=self.project_root, text=True, executable=self.shell)
        else:
            return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, cwd=self.project_root,
                                    text=True, executable=self.shell)
