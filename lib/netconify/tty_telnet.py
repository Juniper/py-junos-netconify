from time import sleep
import telnetlib

from .tty import Terminal

# -------------------------------------------------------------------------
# Terminal connection over TELNET CONSOLE
# -------------------------------------------------------------------------


class Telnet(Terminal):
    RETRY_OPEN = 3                # number of attempts to open TTY
    RETRY_BACKOFF = 2             # seconds to wait between retries

    def __init__(self, host, port, **kvargs):
        """
        :host:
          The hostname or ip-addr of the ternminal server

        :port:
          The TCP port that maps to the TTY device on the
          console server

        :kvargs['timeout']:
          this is the tty read polling timeout.
          generally you should not have to tweak this.
        """
        # initialize the underlying TTY device

        self._tn = telnetlib.Telnet()
        self.host = host
        self.port = port
        self.timeout = kvargs.get('timeout', self.TIMEOUT)
        self.baud = kvargs.get('baud', 9600)
        self._tty_name = "{0}:{1}".format(host, port)

        Terminal.__init__(self, **kvargs)

    # -------------------------------------------------------------------------
    # I/O open close called from Terminal class
    # -------------------------------------------------------------------------

    def _tty_open(self):
        retry = self.RETRY_OPEN
        while retry > 0:
            try:
                self._tn.open(self.host, self.port, self.timeout)
                break
            except Exception as err:
                retry -= 1
                self.notify("TTY busy", "checking back in {0} ...".format(self.RETRY_BACKOFF))
                sleep(self.RETRY_BACKOFF)
        else:
            raise RuntimeError("open_fail: port not ready")

        self.write('\n')

    def _tty_close(self):
        self._tn.close()

    # -------------------------------------------------------------------------
    # I/O read and write called from Terminal class
    # -------------------------------------------------------------------------

    def write(self, content):
        # If baud set to 0 write full speed
        if (int(self.baud) == 0):
            self._tn.write(content + '\n')
            return None

        # Write data according to defined baud
        # per 8 bit of data there are 2 additional bits on the line
        # (parity and stop bits)
        for char in content:
            self._tn.write(char)
            wtime = 10/float(self.baud)
            sleep(wtime)                          # do not remove
        self._tn.write('\n')

    def rawwrite(self, content):
        # If baud set to 0 write full speed
        if (int(self.baud) == 0):
            self._tn.write(content + '\n')
            return None

        # Write data according to defined baud
        # per 1 byte of data there are 2 additional bits on the line
        # (parity and stop bits)
        for char in content:
            self._tn.write(char)
            wtime = 10/float(self.baud)
            sleep(wtime)                          # do not remove
        self._tn.write('\n’)

    def read(self):
        """ read a single line """
        return self._tn.read_until('\n', self.EXPECT_TIMEOUT)

    def read_prompt(self):
        got = self._tn.expect(Terminal._RE_PAT, self.EXPECT_TIMEOUT)
        sre = got[1]

        if 'in use' in got[2]:
            raise RuntimeError("open_fail: port already in use")

        # (buffer, RE group)
        return (None, None) if not got[1] else (got[2], got[1].lastgroup)
