import os, sys
import argparse
from ConfigParser import SafeConfigParser

class netconifyCmdline(object):
  PREFIX = '/etc/netconify'
  INVENTORY = 'hosts'             # in PREFIX

  ### -------------------------------------------------------------------------
  ### CONSTRUCTOR
  ### -------------------------------------------------------------------------

  def __init__(self):
    self._setup_argsparser()
    self._inv = None
    self._name = None



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

    p.add_argument('-i','--inventory', default=self.INVENTORY,
      help='inventory file of named NOOB devices and variables')

    p.add_argument('-M','--model',
      help="Junos device model, used to identify skel file")

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
      
      self._args = self._argsparser.parse_args()
      if self._args.inventory is not None:
        self._ld_inv()

      if self._args.name is not None:
        if self._inv is None:
          raise RuntimeError('need_inv')
        self._set_namevars()

    except RuntimeError as rterr:
      self._err_hanlder(rterr)

  def _err_hanlder(self, err):
    sys.stderr.write("ERROR: {}\n".format(err.message))
    sys.exit(1)

  ### -------------------------------------------------------------------------
  ### load the inventory file
  ### -------------------------------------------------------------------------

  def _ld_inv(self):
    # Load the inventory file.  This file contains the global and per-name
    # variables that will be used to render configuration templates.
    inv_path = self._getpath(self._args.inventory)

    if inv_path is None:
      raise RuntimeError('no_inventory')

    self._inv = SafeConfigParser()
    self._inv.read(inv_path)

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

  def _getpath(self, given):
    inv_path = self._args.inventory

    if os.path.isabs(inv_path):
      if os.path.isfile(inv_path): return inv_path
    else:
      # first check to see if the given path is a valid
      # relative file, and use it if it is.
      if os.path.isfile(inv_path):
        return inv_path
      else:
        # then join the prefix to the path to let the user
        # refer to a file that's in the prefix directory
        inv_path = os.path.join(self._args.prefix, inv_path)
        if os.path.isfile(inv_path): 
          return inv_path
    return None




