import serial
import re
from time import sleep
from datetime import datetime, timedelta

from .xmlmode import xmlmode_netconf

__all__ = ['Serial']

##### =========================================================================
##### Serial class
##### =========================================================================

_RE_PAT_login = '(?P<login>ogin:)\s*'
_RE_PAT_passwd = '(?P<passwd>assword:)\s*'
_RE_PAT_shell = '(?P<shell>%\s*)'

_RE_prompt = re.compile('{}|{}|{}$'.format(_RE_PAT_login,_RE_PAT_passwd,_RE_PAT_shell))
_RE_login = re.compile(_RE_PAT_login)
_RE_shell = re.compile(_RE_PAT_shell)
_RE_passwd_or_shell = re.compile("{}|{}$".format(_RE_PAT_passwd,_RE_PAT_shell))

class Serial(object):
  """
  Serial is used to bootstrap Junos New Out of the Box (NOOB) device
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

  def __init__(self, port='/dev/ttyUSB0', **kvargs):
    """
    :port:
      the serial port, defaults to USB0 since this

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
    self.user = kvargs.get('user','root')
    self.passwd = kvargs.get('passwd','')

    # setup the serial port, but defer open to :login():
    self._ser = serial.Serial()    
    self._ser.port = port
    self._ser.timeout = kvargs.get('timeout', self.TIMEOUT)

    # misc setup
    self.nc = xmlmode_netconf( self._ser )
    self.state = self._ST_INIT
    self.facts = {}

  ##### -----------------------------------------------------------------------
  ##### I/O read and write
  ##### -----------------------------------------------------------------------
  
  def write(self, content):
    """ write the :context: to the serial port and then immediately flush """
    self._ser.write(content+'\n')
    self._ser.flush()

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
      line = self._ser.readline()
      if not line: continue
      rxb += line
      found = expect.search( rxb ) 
      if found is not None: break         # done reading
    else:
      # exceeded the while loop timeout
      return (None,None)

    return (rxb, found.lastgroup)

  def sysctl(self,item):
    rd = self.write('sysctl {}'.format(item))
    return rd.split(': ')[1].split('\r')[0]

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
        self._ser.write("<rpc><close-session/></rpc>")
        return _RE_shell
      else:
        # assume this was a bad login
        raise RuntimeError('login_failed')

    def _ev_shell():
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


  def login(self, attempt = 0):
    """
    open the serial connection and login.  once the login
    is successful, start the netconf XML API
    """
    self._ser.open()    
    self.write('\n\n\n')

    # run through the console login process
    print "logging in ... "

    self.state = self._ST_INIT
    self._login_state_machine(_RE_prompt)

    # now start NETCONF XML 
    print "starting NETCONF ..."
    self.nc.open()
    return True

  def logout(self):
    """
    close down the NETCONF session and cleanly logout of the 
    serial console port
    """
    # close the NETCONF XML

    print "logging out ..."
    if self.nc.hello is not None:
      self.nc.close()

    # assume at unix-shell
    self.write('\n')
    self.read( expect=_RE_shell )
    self._ser.write('exit\n')
    self._ser.flush()
    self._ser.close()
    return True


  