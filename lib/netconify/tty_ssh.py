from select import select
import paramiko
import re
from time import sleep
from .tty import Terminal

_PROMPT = re.compile('|'.join(Terminal._RE_PAT))


class SecureShell(Terminal):
    RETRY_BACKOFF = 2  # seconds to wait between retries
    SSH_LOGIN_RETRY = 1  # number off ssh login retry to console server
    SELECT_WAIT = 0.1
    RECVSZ = 1024

    def __init__(self, host, port, s_user, s_passwd, **kvargs):
        """
        Utility Constructor
        """
        self._ssh = paramiko.SSHClient()
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.host = host
        self.port = port
        self.s_user = s_user
        self.s_passwd = s_passwd
        self.timeout = kvargs.get('timeout', self.TIMEOUT)
        self.attempts = self.SSH_LOGIN_RETRY
        self._tty_name = "{0}:{1}:{2}:{3}".format(host, port, s_user, s_passwd)

        Terminal.__init__(self, **kvargs)

    def _tty_open(self):
        while self.attempts > 0:
            try:
                self._ssh.connect(hostname=self.host, port=int(self.port),
                                  username=self.s_user, password=self.s_passwd, timeout=self.timeout, allow_agent=False,
                                  look_for_keys=False)
                break
            except paramiko.AUTH_FAILED:
                self.notify("Authentication failed when connecting to %s".format(self.host))
            except paramiko.PasswordRequiredException:
                self.notify("Bad username when connecting to %s".format(self.host))
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

    def rawwrite(self, data):
        """ write data only"""
        self._chan.send(data)

    def read(self):
        """
        read a single line
        this is and ugly hack to mimick serial and telnet which reads one byte at a time
        """
        gotr = []
        while True:
            data = self._chan.recv(1)
            if data is None or len(data) <= 0:
                raise ValueError('Unable to detect device prompt')
            elif '\n' in data:
                self._prompt = data.split('\n')[0].strip()
                break
            else:
                gotr.append(data)

        self._rt = ''.join(str(s) for s in gotr)
        return self._rt

    def _tty_close(self):
        """ Close the SSH client channel """
        self._chan.close()

    def read_prompt(self):
        chan = self._chan
        got = []
        while True:
            rd, wr, err = select([chan], [], [], self.SELECT_WAIT)
            if rd:
                data = chan.recv(self.RECVSZ)
                got.append(data)
                found = _PROMPT.search(data)
                if found is not None:
                    break
        return (got, found.lastgroup)
