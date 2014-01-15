from .tty_terminal import Terminal

##### -------------------------------------------------------------------------
##### Terminal connection over TELNET CONSOLE
##### -------------------------------------------------------------------------

class Telnet(Terminal):
  def __init__(self, port, **kvargs):
    """
    :port:
      should be in format of ip_addr[:telnetport] where telnetport defaults
      to standard TELNET port
    """
    Terminal.__init__(self, port, **kvargs)

  def _tty_dev_init(self, port, kvargs):
    # setup the serial port, but defer open to :login():
    self._telnet = telnetlib.Telnet()    

  def _tty_dev_open(self):
    self._telnet.open(self.port)    

  def _tty_dev_close(self):
    self._telnet.write('exit\n')
    self._telnet.close()

  def _tty_dev_write(self,content):
    """ write the :context: to the serial port and then immediately flush """
    self._telnet.write(content+'\n')

  def _tty_dev_rawwrite(self,content):
    self._telnet.write(content)

  def _tty_dev_flush(self):
    pass

  def _tty_dev_read(self):
    return self._telnet.read_until('\n')        

  def write(self, content):
    self._tty_dev_write(content)

  def read(self, expect ):
    got = self._telnet.expect([expect], timeout=5)
    if got[1] is None:
      import pdb
      pdb.set_trace()

    return (got[2],got[1].lastgroup)



