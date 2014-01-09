import pdb

import os, sys
import argparse
import jinja2
from ConfigParser import SafeConfigParser
from getpass import getpass

import netconify

class netconifyCmdo(object):
  PREFIX = '/etc/netconify'
  INVENTORY = 'hosts'                    # in PREFIX

  ### -------------------------------------------------------------------------
  ### CONSTRUCTOR
  ### -------------------------------------------------------------------------

  def __init__(self):
    self._setup_argsparser()
    self._inv = None                    # SafeConfigParser
    self._name = None                   # str
    self._namevars = {}                 # vars for the named NOOB
    self._tty = None                    # jnpr.netconfigy.Serial

  ### -------------------------------------------------------------------------
  ### Command Line Arguments Parser 
  ### -------------------------------------------------------------------------

  def _setup_argsparser(self):
    p = argparse.ArgumentParser(add_help=True)
    self._argsparser = p

    p.add_argument('name', nargs='?', 
      help='name of Junos NOOB device')

    p.add_argument('--prefix', default=self.PREFIX, 
      help='path to etc files')

    p.add_argument('-i','--inventory', 
      help='inventory file of named NOOB devices and variables')

    p.add_argument('--dry-run', action='store_true', default=False,
      dest='dry_run_mode',
      help='dry-run builds the config only')

    p.add_argument('--save', nargs='?', dest='save_conf_path',
      help="save a copy the NOOB conf file")

    ## ------------------------------------------------------------------------
    ## Explicit controls to select the NOOB conf file, vs. netconify
    ## auto-detecting based on read parameters
    ## ------------------------------------------------------------------------

    p.add_argument('-M','--model', dest='EXPLICIT_model',
      help="EXPLICIT: Junos device model, conf from skel dir")

    p.add_argument('-C', '--conf', dest='EXPLICIT_conf',
      help="EXPLICIT: Junos NOOB conf file")

    ## ------------------------------------------------------------------------
    ## serial port configuration
    ## ------------------------------------------------------------------------

    p.add_argument('-P','--port', default='/dev/ttyUSB0',
      help="serial port device")

    p.add_argument('--baud', default='9600',
      help="serial port baud rate")

    ## ------------------------------------------------------------------------
    ## login configuration
    ## ------------------------------------------------------------------------

    p.add_argument('-u','--user', default='root',
      help='login user name')

    p.add_argument('-p','--passwd', default='',
      help='login user password. Alternatively use -k option to prompt')

    p.add_argument('-k', action='store_true', dest='passwd_prompt', default=False)

  ### -------------------------------------------------------------------------
  ### run command line tool
  ### -------------------------------------------------------------------------

  def run(self):
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
        self._dry_run()
        sys.exit(0)        

      # login to the NOOB over the serial port and perform the 
      # needed configuration

      self._netconify()

    except RuntimeError as rterr:
      self._err_hanlder(rterr)

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
    serargs = {}
    serargs['port'] = self._args.port
    serargs['baud'] = self._args.baud
    serargs['user'] = self._args.user 
    serargs['passwd'] = self._args.passwd 

    self._tty = netconify.Serial(**serargs)
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
    self._notify('conf','loading into device ...')

    rc = self._tty.nc.load(content=self.conf)
    if rc is not True:
      raise RuntimeError('load_error')

    self._notify('conf','commit ... please be patient')
    rc = self._tty.nc.commit()
    if rc is not True:
      raise RuntimeError('commit_error')

    self._tty_logout()

  ### -------------------------------------------------------------------------
  ### dry-run mode is used to create the configuraiton file only
  ### -------------------------------------------------------------------------

  def _dry_run(self):
    # if we're giving the EXPLICIT information so we don't need to connect
    # to the device over the console, then simply use the information we've
    # got and build the config.

    # start with checking for an explicit path to a conf file
    path = self._args.EXPLICIT_conf

    # and then check for a model reference

    expl_model = self._args.EXPLICIT_model or self._namevars.get('--model')
    if path is None and expl_model is not None:
      path = os.path.join(self._args.prefix, 'skel', expl_model+'.conf')

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

    self._conf_build(path)
    self._conf_save()

  def _conf_build(self, path):
    if not os.path.isfile(path):
      raise RuntimeError('no_file:{}'.format(path))

    conf = open(path,'r').read()    
    self.conf = jinja2.Template(conf).render(self._namevars)

  def _conf_save(self):
    of_name = self._args.save_conf_path or self._name+'.conf'
    self._notify('conf','saving: {}'.format(of_name))
    with open(of_name,'w+') as f: f.write(self.conf)

  ### -------------------------------------------------------------------------
  ### load the inventory file
  ### -------------------------------------------------------------------------

  def _ld_inv(self, path):
    self._inv = SafeConfigParser()
    rd_files = self._inv.read(path)
    if not len(rd_files):
      raise RuntimeError('no_inv')

  ### -------------------------------------------------------------------------
  ### setup the name variables dictionary
  ### -------------------------------------------------------------------------

  def _set_namevars(self):
    # see if the name exists in the inventory.  if not, then
    # raise an error.
    if not self._inv.has_section(self._args.name):
      raise RuntimeError("no_name")

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
