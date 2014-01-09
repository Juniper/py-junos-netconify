import pdb

import serial
import re
from time import sleep

from .xmlmode import xmlmode_netconf

__all__ = ['netconify']

##### =========================================================================
##### netconify class
##### =========================================================================

_RE_PAT_login = '(?P<login>ogin:)\s*'
_RE_PAT_passwd = '(?P<passwd>assword:)\s*'
_RE_PAT_shell = '(?P<shell>%\s*)'

_RE_prompt = re.compile('{}|{}|{}$'.format(_RE_PAT_login,_RE_PAT_passwd,_RE_PAT_shell))
_RE_login = re.compile(_RE_PAT_login)
_RE_shell = re.compile(_RE_PAT_shell)
_RE_passwd_or_shell = re.compile("{}|{}$".format(_RE_PAT_passwd,_RE_PAT_shell))

class netconify(object):
  TIMEOUT = 0.2

  def __init__(self, port='/dev/ttyUSB0', **kvargs):
    self._ser = serial.Serial()    # this opens the port as well
    self._ser.port = port
    self.user = kvargs.get('user','root')
    self.passwd = kvargs.get('passwd','')
    self._ser.timeout = kvargs.get('timeout', self.TIMEOUT)
    self._ser.open()
    self.facts = {}
    self.nc = xmlmode_netconf( self._ser )

  def write(self, content):
    self._ser.write(content+'\n')
    self._ser.flush()

  def read(self, expect=_RE_prompt ):
    rxb = ''
    while True:
      sleep(self._ser.timeout)
      line = self._ser.readline()
      if not line: continue
      rxb += line
      found = expect.search( rxb ) 
      if found is not None: break

    return (rxb, found.lastgroup)

  def sysctl(self,item):
    rd = self.write('sysctl {}'.format(item))
    return rd.split(': ')[1].split('\r')[0]

  def _login_state_machine(self, expect, attempt=0):
    if 10 == attempt: return False

    prompt,found = self.read(expect)

#    print "IN:{}: {}".format(found, prompt)

    def _ev_login():
      self.write(self.user)
      return _RE_passwd_or_shell

    def _ev_passwd():
      self.write(self.passwd)
      return _RE_shell

    def _ev_hungnetconf():
      # assume we're in a hung state from XML-MODE
      # and will put us back into shell
      self.write("<close-session/>")
      return _RE_shell

    def _ev_shell():
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
    self.write('\n')
    self._login_state_machine(_RE_prompt)

    # -------------------------------------------------------------------------
    # at unix shell
    # -------------------------------------------------------------------------

    # @@@ need to handle the case when there is a password
    # self.facts['ostype'] = self.sysctl('kern.ostype')
    # self.facts['version'] = self.sysctl('kern.version')
    # self.facts['model'] = self.sysctl('hw.product.model').upper()

  def logout(self):
    self._ser.write('exit\n')
    self._ser.close()


  