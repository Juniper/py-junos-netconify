import os, sys
import argparse
from ConfigParser import SafeConfigParser
from getpass import getpass

import jnpr.netconify

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

    p.add_argument('--dry-run',
      help="dry-run builds the config")

    ## ------------------------------------------------------------------------
    ## Explicit controls to select the NOOB conf file, vs. netconify
    ## auto-detecting based on read parameters
    ## ------------------------------------------------------------------------

    p.add_argument('-M','--model',
      help="EXPLICIT: Junos device model")

    p.add_argument('-C', '--conf',
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

      # time to login to the NOOB over the serial port

      serargs = {}
      serargs['port'] = self._args.port
      serargs['baud'] = self._args.baud
      serargs['user'] = self._args.user 
      serargs['passwd'] = self._args.passwd 

      self._tty = jnpr.netconify.Serial(**serargs)
      self._netconify()

    except RuntimeError as rterr:
      self._err_hanlder(rterr)

  def _err_hanlder(self, err):
    sys.stderr.write("ERROR: {}\n".format(err.message))
    sys.exit(1)

  ### -------------------------------------------------------------------------
  ### run through the netconification process
  ### -------------------------------------------------------------------------

  def _netconify(self):
    ok = self._tty.login()
    if not ok:
      raise RuntimeError('no_login')

    self._tty.logout()

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

    self._namevars.update(dict(self._inv.items(self._name)))

