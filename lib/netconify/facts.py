import re
from lxml.builder import E
from lxml import etree

class Facts(object):

  def __init__(self,parent):
    self.rpc = parent.rpc
    self.facts = {}

  @property
  def items(self):
    return self.facts
  
  def version(self):
    rsp = self.rpc('get-software-information')
    pkginfo = rsp.xpath('.//package-information[name = "junos"]/comment')[0].text    

    self.facts['version'] = re.findall(r'\[(.*)\]', pkginfo)[0]
    self.facts['hostname'] = rsp.findtext('host-name')

  def chassis(self):
    rsp = self.rpc('get-chassis-inventory')
    self.inventory = rsp    # keep this since we want to save the data to file
    chas = rsp.find('chassis')
    sn = chas.findtext('serial-number')
    self.facts['model'] = chas.findtext('description').upper()

    # use the chassis level serial number, and if that doesn't exist
    # look for the 'Backplane' serial number
    self.facts['serialnumber'] = sn if sn is not None else \
      chas.xpath('chassis-module[name="Backplane"]/serial-number')[0].text

  def eth(self,ifname):
    cmd = E('get-interface-information',
        E.media(),
        E('interface-name', ifname))

    rsp = self.rpc(etree.tostring(cmd))[0]   # at physical-interface
    facts = self.facts

    facts[ifname] = {}
    facts[ifname]['macaddr'] = rsp.findtext('.//current-physical-address')
    facts[ifname]['ifindex'] = rsp.findtext('snmp-index')
    facts[ifname]['oper'] = rsp.findtext('oper-status')
    facts[ifname]['admin'] = rsp.findtext('admin-status')
    facts[ifname]['speed'] = rsp.findtext('speed')
    facts[ifname]['duplex'] = rsp.findtext('duplex')

    return facts[ifname]

  def gather(self):
    self.version()
    self.chassis()