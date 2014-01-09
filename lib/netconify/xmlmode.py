import pdb

import re, time
import jinja2
from lxml import etree
from lxml.builder import E

from .facts import Facts

__all__ = ['xmlmode_netconf']

_NETCONF_EOM = ']]>]]>'
_xmlns = re.compile('xmlns=[^>]+')
_xmlns_strip = lambda text: _xmlns.sub('',text)
_junosns = re.compile('junos:')
_junosns_strip = lambda text: _junosns.sub('',text)

##### =========================================================================
##### xmlmode_netconf
##### =========================================================================

class xmlmode_netconf(object):
  """
  provides access to the Junos XML API when bootstraping through the 
  serial console port
  """  

  def __init__(self, serial):
    """
    :serial: is serial.Serial object 
    """
    self._ser = serial
    self.hello = None
    self.facts = Facts(self)

  def _receive(self):
    """ process the XML response into an XML object """
    rxbuf = []
    while True:
      line = self._ser.readline().strip()
      if not line: continue                       # if we got nothin, go again
      if _NETCONF_EOM == line: break              # check for end-of-message
      rxbuf.append(line)

    rxbuf[0] = _xmlns_strip(rxbuf[0])         # nuke the xmlns
    rxbuf[1] = _xmlns_strip(rxbuf[1])         # nuke the xmlns
    rxbuf = map(_junosns_strip, rxbuf)        # nuke junos: namespace

    return etree.XML(''.join(rxbuf))

  def open(self):
    """ start the XML API process and receive the 'hello' message """
    self._ser.write('xml-mode netconf need-trailer\n')
    self._ser.flush()
    while True:
      time.sleep(0.1)
      line = self._ser.readline()
      if line.startswith("<!--"): break

    self.hello = self._receive()

  def gather_facts(self):
    self.facts.gather()

  def load(self, path, **kvargs):
    """
    load-override a Junos 'conf'-style file into the device.  if the
    load is successful, return :True:, otherwise return the XML reply
    structure for further processing

    :path:
      path to Junos conf-style text file on the local system.  this
      file could be a Jinja2 template file; and if so you should
      provide vars=<dict> on the call

    :kvargs['action']:
      determines the load mode.  this is 'override' by default.
      you could set this to merge or replace to perform those actions

    :kvargs['vars']:
      a <dict> of variables.  when this is given, the assumption is
      the conf file is a jinja2 template.  the variables will be 
      rendered into the template before loading into the device.
    """
    action = kvargs.get('action','override')
    conf_text = open(path,'r').read()    

    tvars = kvargs.get('vars')
    if tvars is not None:
      # this indicates that path is a jinja2 template,
      # so we need to Templatize the file and redner the 
      # variables into it.
      conf_text = jinja2.Template(conf_text).render(tvars)

    cmd = E('load-configuration', dict(format='text',action=action),
      E('configuration-text', conf_text )
    )
    rsp = self.rpc(etree.tostring(cmd))
    return rsp if rsp.findtext('.//ok') is None else True

  def commit_check(self):
    """ 
    performs the Junos 'commit check' operation.  if successful return
    :True: otherwise return the response as XML for further processing.
    """
    rsp = self.rpc('<commit-configuration><check/></commit-configuration>')
    return True if 'ok' == rsp.tag else rsp

  def commit(self):
    """ 
    performs the Junos 'commit' operation.  if successful return
    :True: otherwise return the response as XML for further processing.
    """
    rsp = self.rpc('<commit-configuration/>')
    return True if 'ok' == rsp.tag else rsp

  def rollback(self):
    """ rollback that recent changes """
    cmd = E('load-configuration', dict(compare='rollback', rollback="0"))
    return self.rpc(etree.tostring(cmd))

  def rpc(self,cmd):
    """ 
    Write the XML cmd and return the response

    :cmd: is a <str> of the XML command
    Return value is an XML object.  No error checking is performed.
    """

    if not cmd.startswith('<'): cmd = '<{}/>'.format(cmd)
    self._ser.write('<rpc>')
    self._ser.write(cmd)
    self._ser.write('</rpc>')

    rsp = self._receive()
    return rsp[0] # return first child after the <rpc-reply>

  def close(self):
    """ issue the XML API to close the session """
    self._ser.write('<rpc><close-session/></rpc>')
    self._ser.flush()
