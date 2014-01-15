import re
from time import sleep
from datetime import datetime, timedelta

from .tty_netconf import tty_netconf

__all__ = ['Terminal']

##### =========================================================================
##### Terminal class
##### =========================================================================

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
  _ST_NC_HUNG = 5

  _RE_PAT = [
    '(?P<login>ogin:\s*$)',
    '(?P<passwd>assword:\s*$)',
    '(?P<badpasswd>ogin incorrect)',
    '(?P<shell>%\s*$)',
    '(?P<cli>[^\\-]>\s*$)'
  ]  

  ##### -----------------------------------------------------------------------
  ##### CONSTRUCTOR
  ##### -----------------------------------------------------------------------

  def __init__(self, **kvargs):
    """
    :kvargs['user']:
      defaults to 'root'

    :kvargs['passwd']:
      defaults to empty; NOOB Junos devics there is
      no root password initially
    """    
    # logic args
    self.user = kvargs.get('user','root')
    self.passwd = kvargs.get('passwd','')

    # misc setup
    self.nc = tty_netconf( self )
    self.state = self._ST_INIT
    self.notifier = None
    self._badpasswd = 0    

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
    self._tty_open()

    self.notify('login','logging in ...')

    self.state = self._ST_INIT
    self._login_state_machine()

    # now start NETCONF XML 
    self.notify('login','starting NETCONF')
    self.nc.open(at_shell = self.at_shell)    
    return True

  def logout(self):
    """
    cleanly logout of the TTY
    """
    self.notify('logout','logging out ...')

    # close the NETCONF session
    self.nc.close()

    # hit <ENTER> and get back to a prompt
    self.write('\n')
    self.read_prompt()

    # issue the 'exit' command and then cleanly
    # shutdown the TTY. 

    self.write('exit')    
    self._tty_close()

    return True

  ##### -----------------------------------------------------------------------
  ##### TTY login state-machine
  ##### -----------------------------------------------------------------------

  def _login_state_machine(self, attempt=0):
    if 10 == attempt: 
      raise RuntimeError('login_sm_failure')

    prompt,found = self.read_prompt()

#    print "CUR-STATE:{}".format(self.state)
#    print "IN:{}:`{}`".format(found,prompt)

    def _ev_login():
      self.state = self._ST_LOGIN
      self.write( self.user )

    def _ev_passwd():
      self.state = self._ST_PASSWD
      self.write( self.passwd )

    def _ev_bad_passwd():
      self.state = self._ST_BAD_PASSWD
      self.write('\n')
      raise RuntimeError('bad_passwd')

    def _ev_hungnetconf():
      if self._ST_INIT == self.state:
        # assume we're in a hung state from XML-MODE. issue the 
        # NETCONF close command, but set the state to NC_HUNG
#        print "DEBUG: burp netconf."
        self.state = self._ST_NC_HUNG
        self.nc.close(force=True)

    def _ev_shell():
      if self.state == self._ST_INIT:
        # this means that the shell was left
        # open.  probably not a good thing,
        # so issue a notify, but move on.
        self.notify('login','shell login was open!')

      self.at_shell = True
      self.state = self._ST_DONE      
      # if we are here, then we are done

    def _ev_cli():
      if self.state == self._ST_INIT:
        # in bad state, return now and retry        
#        print "DEUBG: burp cli."
        return

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
      # if we are here, then loop the event again
      self._login_state_machine(attempt+1)
