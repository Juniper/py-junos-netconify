import re
from time import sleep
from datetime import datetime, timedelta

from .tty_netconf import tty_netconf

__all__ = ['Terminal']

##### =========================================================================
##### Serial class
##### =========================================================================

# _RE_PAT_login = '(?P<login>ogin:\s?$)'
# _RE_PAT_passwd = '(?P<passwd>assword:\s?$)*'
# _RE_PAT_shell = '(?P<shell>%\s?$)'
# _RE_PAT_cli = '(?P<cli>>\s?$)'

# _RE_prompt = re.compile('{}|{}|{}'.format(_RE_PAT_login,_RE_PAT_passwd,_RE_PAT_shell))
# _RE_login = re.compile(_RE_PAT_login)
# _RE_shell = re.compile(_RE_PAT_shell)
# _RE_passwd_or_shell = re.compile("{}|{}$".format(_RE_PAT_passwd,_RE_PAT_shell))

_RE_PAT_login = '(?P<login>ogin:\s*$)'
_RE_PAT_passwd = '(?P<passwd>assword:\s*$)'
_RE_PAT_bad_passwd = '(?P<badpasswd>ogin incorrect)'
_RE_PAT_shell = '(?P<shell>%\s*$)'
_RE_PAT_cli = '(?P<cli>>\s*$)'

_RE_expect = re.compile("{}|{}|{}|{}|{}".format(_RE_PAT_login,
  _RE_PAT_passwd, _RE_PAT_shell, _RE_PAT_cli, _RE_PAT_bad_passwd))

# _RE_expect = re.compile("{}|{}|{}|{}".format(_RE_PAT_login,
#   _RE_PAT_passwd, _RE_PAT_shell, _RE_PAT_cli))

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
  _ST_BAD_PASSWD = 4

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
    self._badpasswd = 0
    self.notifier = None

  ##### -----------------------------------------------------------------------
  ##### Login/logout 
  ##### -----------------------------------------------------------------------

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
    self._login_state_machine()

    # now start NETCONF XML 
    self.notify('login','starting NETCONF')
    self.nc.open(at_shell = self.at_shell)
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
    self.read(_RE_expect)
    self._tty_dev_close()
    return True

  ##### -----------------------------------------------------------------------
  ##### TTY login state-machine
  ##### -----------------------------------------------------------------------

  def _login_state_machine(self, attempt=0):
    if 10 == attempt: 
      raise RuntimeError('login_sm_failure')

    prompt,found = self.read(_RE_expect)

    print "CUR-STATE:{}".format(self.state)
    print "IN:{}:{}".format(found,prompt)

    def _ev_login():
      self.state = self._ST_LOGIN
      self.write( self.user )

    def _ev_passwd():
      self.state = self._ST_PASSWD
      self.write( self.passwd )

    def _ev_bad_passwd():
      self.state = self._ST_BAD_PASSWD 
      self._badpasswd += 1
      if self._badpasswd > 3:
        raise RuntimeError('bad_passwd')

    def _ev_hungnetconf():
      if self._ST_INIT == self.state:
        # assume we're in a hung state from XML-MODE. issue the 
        # NETCONF close command 
        self.nc.close()

    def _ev_shell():
      self.at_shell = True
      self.state = self._ST_DONE      
      # if we are here, then we are done

    def _ev_cli():
      self.at_shell = False
      self.state = self._ST_DONE

    _ev_tbl = {
      'login': _ev_login,
      'passwd': _ev_passwd,
      'badpasswd': _ev_bad_passwd,
      'shell': _ev_shell,
      'cli': _ev_cli
    }

    _ev_tbl.get(found, _ev_hungnetconf)()

    if self.state == self._ST_DONE:
      return True
    else:
      print "NEW-STATE:{}".format(self.state)
      # if we are here, then loop the event again
      self._login_state_machine(attempt+1)
