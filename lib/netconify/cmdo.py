"""
This file defines the 'netconifyCmdo' class used by the 'netconify' 
shell utility
"""
import os, sys, json
import argparse, jinja2
from ConfigParser import SafeConfigParser
from getpass import getpass

import netconify

class netconifyCmdo(object):
  PREFIX = '/etc/netconify'
  INVENTORY = 'hosts'                    # in PREFIX
  DEFAULT_NAME = 'noob'

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

    # hook functions
    self.on_namevars = kvargs.get('on_namevars')

  ### -------------------------------------------------------------------------
  ### PROPERTIES
  ### -------------------------------------------------------------------------

  @property
  def on_namevars(self):
    return self._hook_on_namevars

  @on_namevars.setter
  def on_namevars(self, value):
    self._hook_on_namevars = value
  
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

    p.add_argument('-M','--model', dest='EXPLICIT_model',
      help="EXPLICIT: Junos device model, identifies file in <prefix>/skel")

    p.add_argument('-C', '--conf', dest='EXPLICIT_conf',
      help="EXPLICIT: Junos NOOB configuration file")

    ## ------------------------------------------------------------------------
    ## controlling options
    ## ------------------------------------------------------------------------

    p.add_argument('--dry-run', action='store_true', default=False,
      dest='dry_run_mode',
      help='dry-run builds the config only')

    p.add_argument('--no-save', action='store_true', default=False,
      help='Prevent files from begin saved into --savedir')

    ## ------------------------------------------------------------------------
    ## directory controls
    ## ------------------------------------------------------------------------

    p.add_argument('--confdir', default=self.PREFIX, 
      dest='prefix',   # hack for now.
      help='override path to etc directory configuration files')

    p.add_argument('--savedir', nargs='?', default='.', 
      help="Files are saved into this directory, CWD by default")

    ## ------------------------------------------------------------------------
    ## tty port configuration
    ## ------------------------------------------------------------------------

    p.add_argument('-P','--port', default='/dev/ttyUSB0',
      help="serial port device")

    p.add_argument('--baud', default='9600',
      help="serial port baud rate")

    p.add_argument('-T', '--telnet',
      help='telnet/terminal server, <host>:<port>')

    ## ------------------------------------------------------------------------
    ## login configuration
    ## ------------------------------------------------------------------------

    p.add_argument('-u','--user', default='root',
      help='login user name, defaults to "root"')

    p.add_argument('-p','--passwd', default='',
      help='login user password, *empty* for NOOB')

    p.add_argument('-k', action='store_true', default=False,
      dest='passwd_prompt', 
      help='prompt for user password')

  ### -------------------------------------------------------------------------
  ### run command line tool
  ### -------------------------------------------------------------------------

  def run(self):
    rc = True
    try:
      
      # build up the necessary NOOB variables

      self._args = self._argsparser.parse_args()
      if self._args.inventory is not None:
        self._ld_inv(path=self._args.inventory)

      if self._args.name is not None:
        if self._inv is None:
          self._ld_inv(path=os.path.join(self._args.prefix, self.INVENTORY))
        self._set_namevars()

      # handle password input if necessary

      if self._args.passwd_prompt is True:
        self._args.passwd = getpass()

      # handle dry-run mode and exit 

      if self._args.dry_run_mode is True:
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
  ### tty routines
  ### -------------------------------------------------------------------------

  def _tty_notifier(tty, event, message):
    print "TTY:{}:{}".format(event,message)

  def _notify(self, event, message):
    print "CMD:{}:{}".format(event,message)

  def _tty_login(self):

    tty_args = {}
    tty_args['user'] = self._args.user 
    tty_args['passwd'] = self._args.passwd 

    if self._args.telnet is not None:
      host,port = self._args.telnet.split(':')
      tty_args['host'] = host
      tty_args['port'] = port
      self._tty = netconify.Telnet(**tty_args)
    else:
      tty_args['port'] = self._args.port      
      tty_args['baud'] = self._args.baud
      self._tty = netconify.Serial(**tty_args)

    self._tty.login( notify=self._tty_notifier )

  def _tty_logout(self):
    self._tty.logout()    

  ### -------------------------------------------------------------------------
  ### NETCONIFY the device!
  ### -------------------------------------------------------------------------

  def _netconify(self):

    self._tty_login()
    self._tty.nc.facts.gather()

    model = self._tty.nc.facts.items['model']
    path = os.path.join(self._args.prefix, 'skel', model+'.conf')

    self._notify('conf','building from: {}'.format(path))
    self._conf_build(path)
    self._facts_save()
    self._notify('conf','loading into device ...')

    ### HACK
    # self._tty_logout()
    # return True
    ### HACK


    rc = self._tty.nc.load(content=self.conf)
    if rc is not True:
      self._notify('conf_ld_err','failure to load configuration, aborting.')
      self._tty.nc.rollback();
      self._tty_logout()
      return False
      ###
      ### --- unreachable ---
      ###      

    self._notify('conf','commit ... please be patient')
    rc = self._tty.nc.commit()
    if rc is not True:
      self._notify('conf_save_err','faiure to commit configuration, aborting.')
      self._tty.nc.rollback()
      self._tty_logout()
      return False
      ###
      ### --- unreachable ---
      ###      

    self._tty_logout()
    return True

  ### -------------------------------------------------------------------------
  ### dry-run mode is used to create the configuraiton file only
  ### -------------------------------------------------------------------------

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

  def _conf_build(self, path):
    """
    template build the configuration and save a copy (unless --no-save)
    """
    if not os.path.isfile(path):
      raise RuntimeError('no_file:{}'.format(path))

    conf = open(path,'r').read()    
    self.conf = jinja2.Template(conf).render(self._namevars)

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
    fname = (self._name or self.DEFAULT_NAME)+'.json'
    path = os.path.join(self._args.savedir, fname)
    self._notify('facts','saving: {}'.format(path))
    as_json = json.dumps(self._tty.nc.facts.items)
    with open(path,'w+') as f: f.write(as_json)

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
