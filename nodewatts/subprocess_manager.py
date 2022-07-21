import os
import subprocess
import logging
import pwd
from typing import Tuple, IO
from .error import NodewattsError
from .config import NWConfig
from .singleton import Singleton
logger = logging.getLogger("Main")


class NWSubprocessError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class NWSubprocessTimeout(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class SubprocessManager(Singleton):
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

    def project_process_async(self, cmd: str, custom_env=None) -> IO:
        if custom_env:
            return subprocess.Popen(cmd, shell=True, user=self.project_user, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, env=custom_env,
                                    cwd=self.project_root, text=True, executable=self.shell)
        else:
            return subprocess.Popen(cmd, shell=True, user=self.project_user, stdout=subprocess.PIPE, 
                                    stderr=subprocess.STDOUT, cwd=self.project_root,
                                    text=True, executable=self.shell)
                         
    def perf_event_process_blocking(self, cmd: str, on_cgroup=None):
        if on_cgroup:
            path = os.path.join(self.perf_root, on_cgroup)
        else:
            path = self.perf_root
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, check=True,
                                      cwd=path, text=True, executable=self.shell)
        except subprocess.CalledProcessError as e:
            out = ("" if e.stdout is None else e.stdout)
            err = ("" if e.stderr is None else e.stderr)
            raise NWSubprocessError("Command: " + cmd + " failed with exit code " + str(e.returncode)
                                    + " \nstdout dump: \n" + out + " \n stderr dump: \n" + err) from None
        else:
            return (proc.stdout, proc.stderr)