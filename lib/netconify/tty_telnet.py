import telnetlib
from .tty import Terminal

##### -------------------------------------------------------------------------
##### Terminal connection over TELNET CONSOLE
##### -------------------------------------------------------------------------

class Telnet(Terminal):
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
    self._tty_name = "{}:{}".format(host,port)

    Terminal.__init__(self, **kvargs)  

  ### -------------------------------------------------------------------------
  ### I/O open close called from Terminal class
  ### -------------------------------------------------------------------------

  def _tty_open(self):
    try:
      self._tn.open(self.host,self.port,self.timeout)
    except:
      raise RuntimeError("open_fail: port not ready")      
    self.write('\n')

  def _tty_close(self):
    self._tn.close()

  ### -------------------------------------------------------------------------
  ### I/O read and write called from Terminal class
  ### -------------------------------------------------------------------------

  def write(self, content):
    """ write content + <ENTER> """
    self._tn.write(content+'\n')

  def rawwrite(self,content):
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
    return (None,None) if not got[1] else (got[2], got[1].lastgroup)
