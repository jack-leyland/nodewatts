import os
import subprocess
import logging
import pwd
from typing import Tuple
from psutil import Process
import psutil

from nodewatts.error import NodewattsError
from nodewatts.config import NWConfig
logger = logging.getLogger("Main")


class NWSubprocessError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWSubprocessTimeout(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class SubprocessManager():
    def __init__(self, conf: NWConfig):
        self.project_root = conf.root_path
        self.project_user = conf.user
        self.nodewatts_root = os.getcwd()
        self.entry_path = os.path.join(conf.root_path, conf.entry_file)
        logger.debug("Process manager started.")
        self.shell = conf.subprocess_shell_path
        self.perf_root = '/sys/fs/cgroup/perf_event'

    @staticmethod
    def demote_child(user_uid, user_gid):
        def result():
            os.setgid(user_gid)
            os.setuid(user_uid)
        return result
    
    @staticmethod
    def prep_user_process(username: str, cwd: str, env_vars=None) -> Tuple[dict[str, str], int, int]:
        pw_record = pwd.getpwnam(username)
        homedir = pw_record.pw_dir
        user_uid = pw_record.pw_uid
        user_gid = pw_record.pw_gid
        env = os.environ.copy()
        env.update({'HOME': homedir, 'LOGNAME': username, 'PWD': cwd, 'USER': username})
        if env_vars:
            env.update(env_vars)
        return (env, user_uid, user_gid)

    # Execute a blocking commmand in the target Node project's root directory as the provide non-root user.
    # Raises SubprocessError if non zero return code, otherwise returns output of process
    # Used mainly for handling npm dependecies required by the tool
    def project_process_blocking(self, cmd: str, custom_env=None, timeout=None, inject_to_path=None) -> Tuple[str, str]:
        if custom_env:
            env, uid, gid = self.prep_user_process(self.project_user, self.project_root, custom_env)
        else:
            env, uid, gid = self.prep_user_process(self.project_user, self.project_root)

        if inject_to_path:
            env["PATH"] += os.pathsep + inject_to_path
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, check=True, preexec_fn=self.demote_child(uid,gid), 
            start_new_session=True, cwd=self.project_root, text=True, executable=self.shell, env=env, timeout=timeout)
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

    # Executes a command asynchronously from project root dir as non-root user
    # such that it will not block the spawning of further subprocesses.
    # Used mainly to run the web server during profiling.
    # Unlike the blocking methods, aync process spawn methods will return the
    # process instance such that the caller can verify it is still alive before
    # running others jobs that depend on it.

    def project_process_async(self, cmd: str, custom_env=None, inject_to_path=None) -> subprocess.Popen:
        if custom_env:
            env, uid, gid = self.prep_user_process(self.project_user, self.project_root, custom_env)
        else:
            env, uid, gid = self.prep_user_process(self.project_user, self.project_root)
        if inject_to_path:
            env["PATH"] += os.pathsep + inject_to_path
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=env, preexec_fn=self.demote_child(uid,gid), 
                                cwd=self.project_root, text=True, executable=self.shell, start_new_session=True)

                         
    def perf_event_process_blocking(self, cmd: str) -> Tuple[str, str]:
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, check=True,
                                      cwd=self.perf_root, text=True, executable=self.shell)
        except subprocess.CalledProcessError as e:
            out = ("" if e.stdout is None else e.stdout)
            err = ("" if e.stderr is None else e.stderr)
            raise NWSubprocessError("Command: " + cmd + " failed with exit code " + str(e.returncode)
                                    + " \nstdout dump: \n" + out + " \n stderr dump: \n" + err) from None
        else:
            return (proc.stdout, proc.stderr)

    def nodewatts_process_async(self, cmd: str) -> subprocess.Popen:
        return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, cwd=os.getcwd(), 
                                text=True, executable=self.shell, start_new_session=True)

    def nodewatts_process_blocking(self, cmd:str) -> Tuple[str, str]:
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, check=True,
                                     text=True, executable=self.shell)
        except subprocess.CalledProcessError as e:
            out = ("" if e.stdout is None else e.stdout)
            err = ("" if e.stderr is None else e.stderr)
            raise NWSubprocessError("Command: " + cmd + " failed with exit code " + str(e.returncode)
                                    + " \nstdout dump: \n" + out + " \n stderr dump: \n" + err) from None 
        else:
            return (proc.stdout, proc.stderr)    

    #Terminates only if exists, does nothing otherwise
    @staticmethod
    def terminate_process_tree(pid: str) -> None:
        if not psutil.pid_exists(pid): return
        parent = Process(pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
    
    @staticmethod
    def kill_process_tree(pid: str) -> None:
        if not psutil.pid_exists(pid): return
        parent = Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()

    @staticmethod
    def pid_exists(pid: str) -> bool:
        return psutil.pid_exists(pid)