import serial, telnetlib
import re
from time import sleep
from datetime import datetime, timedelta

from .tty_netconf import tty_netconf

__all__ = ['Serial', 'Telnet']

##### =========================================================================
##### Serial class
##### =========================================================================

_RE_PAT_login = '(?P<login>ogin:)\s*'
_RE_PAT_passwd = '(?P<passwd>assword:)\s*'
_RE_PAT_shell = '(?P<shell>%\s*)'
_RE_PAT_cli = '(?P<cli>>\s*)'

_RE_prompt = re.compile('{}|{}|{}$'.format(_RE_PAT_login,_RE_PAT_passwd,_RE_PAT_shell))
_RE_login = re.compile(_RE_PAT_login)
_RE_shell = re.compile(_RE_PAT_shell)
_RE_passwd_or_shell = re.compile("{}|{}$".format(_RE_PAT_passwd,_RE_PAT_shell))

class Terminal(object):
  """
  Terminal is used to bootstrap Junos New Out of the Box (NOOB) device
  over the CONSOLE port.  The general use-case is to setup the minimal
  configuration so that the device is IP reachable using SSH
  and NETCONF for remote management.

  Serial is needed for Junos devices that do not support
  the DHCP 'auto-installation' or 'ZTP' feature; i.e. you *MUST*
  to the NOOB configuration via the CONSOLE.  

  Serial is also useful for situations even when the Junos
  device supports auto-DHCP, but is not an option due to the
  specific situation
  """
  TIMEOUT = 0.2           # serial readline timeout, seconds
  EXPECT_TIMEOUT = 10     # total read timeout, seconds

  _ST_INIT = 0
  _ST_LOGIN = 1
  _ST_PASSWD = 2
  _ST_DONE = 3

  ##### -----------------------------------------------------------------------
  ##### CONSTRUCTOR
  ##### -----------------------------------------------------------------------

  def __init__(self, port, **kvargs):
    """
    :port:
      identifies the tty port, as provided by the subclass

    :kvargs['user']:
      defaults to 'root'

    :kvargs['passwd']:
      defaults to empty; NOOB Junos devics there is
      no root password initially

    :kvargs['timeout']:
      this is the serial readline() polling timeout.  
      generally you should not have to tweak this.
    """
    # init args
    self.port = port
    self.user = kvargs.get('user','root')
    self.passwd = kvargs.get('passwd','')

    # initialize the underlying TTY device
    self._tty_dev_init(port, kvargs)

    # misc setup
    self.nc = tty_netconf( self )
    self.state = self._ST_INIT
    self.notifier = None

  ##### -----------------------------------------------------------------------
  ##### Login/logout 
  ##### -----------------------------------------------------------------------

  def _login_state_machine(self, expect, attempt=0):
    if 10 == attempt: return False

    prompt,found = self.read(expect)

#    print "IN:{}: {}".format(found, prompt)

    def _ev_login():
      self.state = self._ST_LOGIN
      self.write(self.user)
      return _RE_passwd_or_shell

    def _ev_passwd():
      self.state = self._ST_PASSWD
      self.write(self.passwd)
      return _RE_shell

    def _ev_hungnetconf():
      if self._ST_INIT == self.state:
        # assume we're in a hung state from XML-MODE
        # issue the close command and then we expect
        # to be back at the unix shell
        self._tty_dev_rawwrite("<rpc><close-session/></rpc>")
        return _RE_shell
      else:
        # assume this was a bad login
        raise RuntimeError('login_failed')

    def _ev_shell():
#      print "DEBUG:{}".format(prompt)
      self.state = self._ST_DONE      
      # if we are here, then we are done
      return None

    _ev_tbl = {
      'login': _ev_login,
      'passwd': _ev_passwd,
      'shell': _ev_shell
    }

    expect = _ev_tbl.get(found, _ev_hungnetconf)()

    if expect is None: 
      return True
    else:
      # if we are here, then loop the event again
#      print "OUT:{}".format(expect.pattern)
      self._login_state_machine(expect, attempt+1)


  def notify(self,event,message):
    if not self.notifier: return
    self.notifier(event,message)

  def login(self, notify=None):
    """
    open the serial connection and login.  once the login
    is successful, start the netconf XML API
    """
    self.notifier = notify
    self.notify('login','connecting to terminal port ...')    
    self._tty_dev_open()
    self.write('\n\n\n')

    self.notify('login','logging in ...')
    self.state = self._ST_INIT
    self._login_state_machine(_RE_prompt)

    # now start NETCONF XML 
    self.notify('login','starting NETCONF')
    self.nc.open()
    return True

  def logout(self):
    """
    close down the NETCONF session and cleanly logout of the 
    serial console port
    """
    # close the NETCONF XML

    self.notify('logout','logging out ...')
    if self.nc.hello is not None:
      self.nc.close()

    # assume at unix-shell
    self.write('\n')
    self.read( expect=_RE_shell )
    self._tty_dev_close()
    return True

##### -------------------------------------------------------------------------
##### Terminal connection over SERIAL CONSOLE
##### -------------------------------------------------------------------------

class Serial(Terminal):
  def __init__(self, port='/dev/ttyUSB0', **kvargs):
    """
    :port:
      the serial port, defaults to USB0 since this
    """
    Terminal.__init__(self, port, **kvargs)

  def _tty_dev_init(self, port, kvargs):
    # setup the serial port, but defer open to :login():
    self._ser = serial.Serial()    
    self._ser.port = port
    self._ser.timeout = kvargs.get('timeout', self.TIMEOUT)

  def _tty_dev_open(self):
    self._ser.open()    

  def _tty_dev_close(self):
    self._ser.write('exit\n')
    self._ser.flush()
    self._ser.close()

  def _tty_dev_write(self,content):
    """ write the :context: to the serial port and then immediately flush """
    self._ser.write(content+'\n')
    self._ser.flush()

  def _tty_dev_rawwrite(self,content):
    self._ser.write(content)

  def _tty_dev_flush(self):
    self._ser.flush()        

  def _tty_dev_read(self):
    return self._ser.readline()    

  def write(self, content):
    self._tty_dev_write(content)

  def read(self, expect=_RE_prompt ):
    """
    reads text from the serial console (using readline) until
    a match is found against the :expect: regular-expression object.
    When a match is found, return a tuple(<text>,<found>) where
    <text> is the complete text and <found> is the name of the 
    regular-expression group. If a timeout occurs, then return 
    the tuple(None,None).
    """
    rxb = ''
    mark_start = datetime.now()
    mark_end = mark_start + timedelta(seconds=self.EXPECT_TIMEOUT)

    while datetime.now() < mark_end:
      sleep(0.1)                          # do not remove
      line = self._tty_dev_read()
      if not line: continue
      rxb += line
      found = expect.search( rxb ) 
      if found is not None: break         # done reading
    else:
      # exceeded the while loop timeout
      return (None,None)

    return (rxb, found.lastgroup)    

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

  def read(self, expect=_RE_prompt ):
    got = self._telnet.expect([expect], timeout=5)
    if got[1] is None:
      import pdb
      pdb.set_trace()

    return (got[2],got[1].lastgroup)



