from select import select
import paramiko
import re
from time import sleep
from .tty import Terminal


class SecureShell(Terminal):
    RETRY_BACKOFF = 2  # seconds to wait between retries
    SSH_LOGIN_RETRY = 3  # number off ssh login retry to console server

    def __init__(self, host, port, user, passwd, **kvargs):
        """
        Utility Constructor
        """
        self._ssh = paramiko.SSHClient()
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.timeout = kvargs.get('timeout', self.TIMEOUT)
        self.attempts = self.SSH_LOGIN_RETRY
        self._tty_name = "{0}:{1}:{2}:{3}".format(host, port, user, passwd)

        Terminal.__init__(self, **kvargs)

    def _tty_open(self):
        while self.attempts > 0:
            try:
                self._ssh.connect(hostname=self.host, port=int(self.port),
                                  username=self.user, password=self.passwd, timeout=self.timeout)
                break
            except paramiko.AUTH_FAILED:
                self.notify("Authentication failed when connecting to %s".format(self.host))
            except paramiko.AuthenticationException:
                self.attempts -= 1
                self.notify("TTY busy", "checking back in {0} ...".format(self.RETRY_BACKOFF))
                sleep(self.RETRY_BACKOFF)
        else:
            raise RuntimeError("open_fail: ssh port not ready")

        self._chan = self._ssh.invoke_shell()
        self.write('\n')

    def write(self, data):
        """ write data + <ENTER> """
        self._chan.send(data)
        self._chan.send('\n')

    def _tty_close(self):
        """ Close the SSH client channel """
        self._chan.close()
