"""
This file defines the 'netconifyCmdo' class.
Used by the 'netconify' shell utility.
"""
import os, sys, json, re
import argparse, jinja2
from ConfigParser import SafeConfigParser
from getpass import getpass
from lxml import etree

import netconify

__all__ = ['netconifyCmdo']

QFX_MODEL_LIST = ['QFX3500','QFX3500S']
QFX_MODE_NODE = 'NODE'
QFX_MODE_SWITCH = 'SWITCH'

class netconifyCmdo(object):
  PREFIX = '/etc/netconify'              # directory of config files
  INVENTORY = 'hosts'                    # in PREFIX
  DEFAULT_NAME = 'noob'                  # when a <name> is not provided

  ### -------------------------------------------------------------------------
  ### CONSTRUCTOR
  ### -------------------------------------------------------------------------

  def __init__(self, **kvargs):
    """
    :kvargs['on_namevars']:
      callback function(<dict>) that allows the caller to
      'munge' the namevars before they are applied into the 
      configuration template file
    """
    self._setup_argsparser()
    self._inv = None                    # SafeConfigParser
    self._name = None                   # str
    self._namevars = {}                 # vars for the named NOOB
    self._tty = None                    # jnpr.netconfigy.Serial
    self._has_changed = False

    # hook functions
    self.on_namevars = kvargs.get('on_namevars')
    self.on_notify = kvargs.get('notify')

  ### -------------------------------------------------------------------------
  ### PROPERTIES
  ### -------------------------------------------------------------------------

  @property
  def on_namevars(self):
    return self._hook_on_namevars

  @on_namevars.setter
  def on_namevars(self, value):
    self._hook_on_namevars = value

  @property
  def changed(self):
    return self._has_changed
  
  ### -------------------------------------------------------------------------
  ### Command Line Arguments Parser 
  ### -------------------------------------------------------------------------

  def _setup_argsparser(self):
    p = argparse.ArgumentParser(add_help=True)
    self._argsparser = p

    ## ------------------------------------------------------------------------
    ## input identifiers
    ## ------------------------------------------------------------------------

    p.add_argument('name', nargs='?', 
      help='name of Junos NOOB device')

    p.add_argument('-i','--inventory', 
      help='inventory file of named NOOB devices and variables')

    ## ------------------------------------------------------------------------
    ## Explicit controls to select the NOOB conf file, vs. netconify
    ## auto-detecting based on read parameters
    ## ------------------------------------------------------------------------

    g = p.add_argument_group('DEVICE controls')

    g.add_argument('-m','--model', dest='EXPLICIT_model',
      help="EXPLICIT: Junos device model, identifies file in <prefix>/skel")

    g.add_argument('-j', '--conf', dest='EXPLICIT_conf',
      help="EXPLICIT: Junos NOOB configuration file")

    g.add_argument('--qfx-node', dest='qfx_mode', 
      action='store_const', const=QFX_MODE_NODE,
      help='Set QFX device into "node" mode')

    g.add_argument('--qfx-switch', dest='qfx_mode', 
      action='store_const', const=QFX_MODE_SWITCH,
      help='Set QFX device into "switch" mode')

    ## ------------------------------------------------------------------------
    ## controlling options
    ## ------------------------------------------------------------------------

    g = p.add_argument_group('MODE controls')
    g.add_argument('--dry-run', action='store_true', default=False,
      dest='dry_run_mode',
      help='dry-run builds the config only')

    g.add_argument('--no-save', action='store_true', default=False,
      help='Prevent files from begin saved into --savedir')

    g.add_argument('-F','--facts', action='store_true',
      dest='only_gather_facts',
      help='Only gather facts and save them into --savedir')

    ## ------------------------------------------------------------------------
    ## directory controls
    ## ------------------------------------------------------------------------

    g = p.add_argument_group('DIR controls')
    g.add_argument('-C','--confdir', default=self.PREFIX, 
      dest='prefix',   # hack for now.
      help='override path to etc directory configuration files')

    g.add_argument('-S','--savedir', nargs='?', default='.', 
      help="Files are saved into this directory, CWD by default")

    ## ------------------------------------------------------------------------
    ## tty port configuration
    ## ------------------------------------------------------------------------

    g = p.add_argument_group('TTY controls')

    g.add_argument('-p','--port', default='/dev/ttyUSB0',
      help="serial port device")

    g.add_argument('-b','--baud', default='9600',
      help="serial port baud rate")

    g.add_argument('-t', '--telnet',
      help='telnet/terminal server, <host>:<port>')

    g.add_argument('--timeout', default='0.5',
      help='TTY connection timeout (s)')

    ## ------------------------------------------------------------------------
    ## login configuration
    ## ------------------------------------------------------------------------

    g = p.add_argument_group("LOGIN controls")
    g.add_argument('-u','--user', default='root',
      help='login user name, defaults to "root"')

    g.add_argument('-P','--passwd', default='',
      help='login user password, *empty* for NOOB')

    g.add_argument('-k', action='store_true', default=False,
      dest='passwd_prompt', 
      help='prompt for user password')

  ### -------------------------------------------------------------------------
  ### run command line tool
  ### -------------------------------------------------------------------------

  def run(self, args=None):
    rc = True
    try:
      
      # build up the necessary NOOB variables
      self._args = self._argsparser.parse_args(args)
      self._name = self._args.name

      if self._args.inventory is not None:
        self._ld_inv(path=self._args.inventory)

      if self._args.name is not None:
        # if we are given a name, lets first try to load the inventory
        if self._inv is None:
          path = os.path.join(self._args.prefix, self.INVENTORY)
          if os.path.isfile(path):
            self._ld_inv(path)
            self._set_namevars()

      # handle password input if necessary
      if self._args.passwd_prompt is True:
        self._args.passwd = getpass()

      # if we just want to collect the facts then
      # execute the dry_run_mode code

      if self._args.only_gather_facts is True:
        rc = self._only_gather_facts()
      elif self._args.qfx_mode is not None:
        rc = self._qfx_mode()
      elif self._args.dry_run_mode is True:
        rc = self._dry_run()
      else:
        rc = self._netconify()

    except RuntimeError as rterr:
      self._err_hanlder(rterr)

    return rc

  def _err_hanlder(self, err):
    sys.stderr.write("ERROR: {}\n".format(err.message))
    sys.exit(1)

  ### -------------------------------------------------------------------------
  ### Notifiers
  ### -------------------------------------------------------------------------

  def _tty_notifier(tty, event, message):
    print "TTY:{}:{}".format(event,message)

  def _notify(self, event, message):
    if self.on_notify is not None:
      self.on_notify(event,message)
    elif self.on_notify is not False:
      print "CMD:{}:{}".format(event,message)

  ### -------------------------------------------------------------------------
  ### tty routines
  ### -------------------------------------------------------------------------

  def _tty_login(self):

    tty_args = {}
    tty_args['user'] = self._args.user 
    tty_args['passwd'] = self._args.passwd 
    tty_args['timeout'] =float(self._args.timeout)

    if self._args.telnet is not None:
      host,port = re.split('[,:]',self._args.telnet)
      tty_args['host'] = host
      tty_args['port'] = port
      self._tty = netconify.Telnet(**tty_args)
    else:
      tty_args['port'] = self._args.port      
      tty_args['baud'] = self._args.baud
      self._tty = netconify.Serial(**tty_args)

    notify = self.on_notify or self._tty_notifier
    self._tty.login( notify=notify )

  def _tty_logout(self):
    self._tty.logout()    

  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  ### -------------------------------------------------------------------------
  ### only gather facts
  ### -------------------------------------------------------------------------
  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  

  def _only_gather_facts(self):
    self._tty_login()
    self._notify('facts','retrieving device facts...')    
    self._tty.nc.facts.gather()
    self._facts_save()
    self._tty_logout()
    return True    

  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  ### -------------------------------------------------------------------------
  ### NETCONIFY the device!
  ### -------------------------------------------------------------------------
  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  def _netconify(self):
    self._tty_login()
    self._notify('facts','retrieving device facts...')    
    self._tty.nc.facts.gather()

    self._conf_build()
    self._facts_save()
    rc = self._push_config()    
    self._tty_logout()

    return rc

  def _push_config(self):
    self._notify('conf','loading into device ...')

    """ push the configuration or rollback changes on error """
    rc = self._tty.nc.load(content=self.conf)
    if rc is not True:
      self._notify('conf_ld_err','failure to load configuration, aborting.')
      self._tty.nc.rollback();
      return False

    self._notify('conf','commit ... please be patient')
    rc = self._tty.nc.commit()
    if rc is not True:
      self._notify('conf_save_err','faiure to commit configuration, aborting.')
      self._tty.nc.rollback()
      return False

    self._notify('conf','commit completed.')
    return True

  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  ### -------------------------------------------------------------------------
  ### dry-run mode is used to create the configuraiton file only
  ### -------------------------------------------------------------------------
  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  def _dry_run(self):
    # see if our config path can be determined from the args, rather
    # than going to the device for model information.

    path = self._conf_fromargs()

    # if we have a path, then we don't need to connect to the device
    # to get the information needed to build the device.

    if path is None:
      # otherwise, we need to login to the device to get the model information
      # so we can use it to lookup the configuration file

      self._tty_login()
      self._tty.nc.facts.gather()
      self._tty_logout()

      model = self._tty.nc.facts.items['model']
      path = os.path.join(self._args.prefix, 'skel', model+'.conf')

    # now build the conf file, and ensure that it will get saved
    self._conf_build(path)    
    return True

  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  ### -------------------------------------------------------------------------
  ### QFX MODE processing
  ### -------------------------------------------------------------------------
  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  

  def _qfx_mode(self):
    need_change = False

    # login to the device and verify that this is a supported QFX node

    try:
      self._tty_login()
    except:
      self._notify('login','Failure to login, check TTY, could be in use already.')
      return False

    self._tty.nc.facts.gather()
    facts = self._tty.nc.facts.items

    # make sure we're logged into a QFX3500 device.
    # set this up as a list check in case we have other models
    # in the future to deal with.

    if facts['model'] not in QFX_MODEL_LIST:
      self._notify('qfx',"Not on a QFX device [{}]".format(facts['model']))
      return False

    now,later = self._qfx_device_mode_get()

    change = bool(later != self._args.qfx_mode)     # compare to after-reoobt
    reboot = bool(now != self._args.qfx_mode)       # compare to now

    self._notify('info',"QFX mode now/later: {}/{}".format(now, later))
    if now == later and later == self._args.qfx_mode:
      # nothing to do
      self._notify('info','No change required')
    else:
      self._notify('info','Action required')
      need_change = True

    # keep a copy of the facts
    self._facts_save()

    if self._args.dry_run_mode is True:
      # then we are all done.
      self._notify('info','dry-run mode: change-needed: {}'.format(need_change))      
      self._has_changed = need_change
      self._tty_logout()
      return True

    if change is True:
      self._notify('change','Changing the mode to: {}'.format(self._args.qfx_mode))
      self._has_changed = True
      self._qfx_device_mode_set()
    if reboot is True:
      self._notify('change','REBOOTING device now!')
      self._has_changed = True      
      self._tty.nc.reboot()
      # no need to close the tty, since the device is rebooting ...
      return True

    self._tty_logout
    return True

  ### -------------------------------------------------------------------------
  ### configuration file build/save methods
  ### -------------------------------------------------------------------------

  def _conf_fromargs(self):
    """ 
    determine configuration file path from any arg overrides.
    returns :None: if there are no overrides
    """
    path = self._args.EXPLICIT_conf

    # and then check for a model reference.  this can come either
    # from the cmdargs or from the --model override in the 
    # inventory file

    expl_model = self._args.EXPLICIT_model or self._namevars.get('--model')
    if path is None and expl_model is not None:
      path = os.path.join(self._args.prefix, 'skel', expl_model+'.conf')

    return path

  def _conf_build(self):
    """
    template build the configuration and save a copy (unless --no-save)
    """

    if self._args.EXPLICIT_conf is None:
      model = self._tty.nc.facts.items['model']
      path = os.path.join(self._args.prefix, 'skel', model+'.conf')
      self._notify('conf','building from: {}'.format(path))
      if not os.path.isfile(path):
        raise RuntimeError('no_file:{}'.format(path))
      conf = open(path,'r').read()    
      self.conf = jinja2.Template(conf).render(self._namevars)
    else:
      path = self._args.EXPLICIT_conf
      if not os.path.isfile(path):
          raise RuntimeError('no_file:{}'.format(path))      
      self.conf = open(path).read()

    if self._args.no_save is False:
      self._conf_save()

  def _conf_save(self):
    """ 
    saves the configuraiton file, either using the <name>
    from the commamnd args or 'noob' as default
    """
    fname = (self._name or self.DEFAULT_NAME)+'.conf'
    path = os.path.join(self._args.savedir, fname)
    self._notify('conf','saving: {}'.format(path))
    with open(path,'w+') as f: f.write(self.conf)

  def _facts_save(self):

    # save basic facts as JSON file
    fname = (self._name or self.DEFAULT_NAME)+'-facts.json'
    path = os.path.join(self._args.savedir, fname)
    self._notify('facts','saving: {}'.format(path))
    as_json = json.dumps(self._tty.nc.facts.items)
    with open(path,'w+') as f: f.write(as_json)

    if hasattr(self._tty.nc.facts,'inventory'):
      # also save the inventory as XML file
      fname = (self._name or self.DEFAULT_NAME)+'-inventory.xml'
      path = os.path.join(self._args.savedir, fname)
      self._notify('inventory','saving: {}'.format(path))
      as_xml = etree.tostring(self._tty.nc.facts.inventory, pretty_print=True)
      with open(path,'w+') as f: f.write(as_xml)

  ### -------------------------------------------------------------------------
  ### load the inventory file
  ### -------------------------------------------------------------------------

  def _ld_inv(self, path):
    """ loads the inventory file contents """
    self._inv = SafeConfigParser()
    rd_files = self._inv.read(path)
    if not len(rd_files):
      raise RuntimeError('no_inv')

  ### -------------------------------------------------------------------------
  ### setup the name variables dictionary
  ### -------------------------------------------------------------------------

  def _set_namevars(self):
    """ 
    setup the namevars for the designated <name>.  these
    vars will be used in the context for template building
    the configuration file.
    """
    # see if the name exists in the inventory.  if not, then
    # raise an error.
    if not self._inv.has_section(self._args.name):
      raise RuntimeError("unknown_name")

    self._name = self._args.name

    # create a dictionary of name variables.  include 
    # the 'all' section first, then apply the per-name
    # section from the inventory file

    self._namevars = {}
    if self._inv.has_section('all'):
      self._namevars.update(dict(self._inv.items('all')))

    # load the named NOOB section and set the hostname if not
    # explicty configured in the inventory file

    self._namevars.update(dict(self._inv.items(self._name)))
    if not self._namevars.has_key('hostname'):
      self._namevars['hostname'] = self._name

    if self._hook_on_namevars is not None:
      # invoke the caller hook so they can
      # munge the namevars before they are applied 
      # into the configuraiton template
      self._hook_on_namevars(self._namevars)

  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  ### -------------------------------------------------------------------------
  ### MISC device RPC commands & controls
  ### -------------------------------------------------------------------------
  ##### !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

  _QFX_MODES = {
    'Standalone': QFX_MODE_SWITCH,
    'Node-device': QFX_MODE_NODE
  }

  _QFX_XML_MODES = {
    QFX_MODE_SWITCH:'standalone', 
    QFX_MODE_NODE:'node-device'
  }

  def _qfx_device_mode_get(self):
    """ get the current device mode """
    rpc = self._tty.nc.rpc
    got = rpc('show-chassis-device-mode')
    now = got.findtext('device-mode-current')
    later = got.findtext('device-mode-after-reboot')
    return (self._QFX_MODES[now], self._QFX_MODES[later])

  def _qfx_device_mode_set(self):
    """ sets the device mode """
    rpc = self._tty.nc.rpc
    mode = self._QFX_XML_MODES[self._args.qfx_mode]
    cmd = '<request-chassis-device-mode><{}/></request-chassis-device-mode>'.format(mode)
    got = rpc(cmd)
    return True
