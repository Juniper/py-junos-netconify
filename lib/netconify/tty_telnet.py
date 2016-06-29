from time import sleep
import telnetlib

from .tty import Terminal

# -------------------------------------------------------------------------
# Terminal connection over TELNET CONSOLE
# -------------------------------------------------------------------------

def _ignore_options(socket, command, option):
    """
    Used as a Telnet.set_option_negotiation_callback() function.

    If no option negotiation callback function is set, telnetlib
    will pass Telnet options back to netconify in the data stream.
    This is especially problematic for the AUTHENTICATION (0x25) option.
    0x25 is an ASCII % character and confuses the login state machine into
    thinking that it is at the shell prompt.
    This function simply receives and ignores Telnet options. This prevents
    the options from appearing in the data stream and confusing the
    login state machine.
    """
    pass

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
        self._tty_name = "{0}:{1}".format(host, port)

        Terminal.__init__(self, **kvargs)

    # -------------------------------------------------------------------------
    # I/O open close called from Terminal class
    # -------------------------------------------------------------------------

    def _tty_open(self):
        retry = self.RETRY_OPEN
        self._tn.set_option_negotiation_callback(_ignore_options)
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
        """ write content + <ENTER> """
        self._tn.write(content + '\n')

    def rawwrite(self, content):
        """ write content as-is """
        self._tn.write(content)

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
