### NOTICE: Under active construction

In the process of streamlining the functionality based on recent use-cases, etc.  Please be advised that the README below is out of date at the momement.  The original code has been backed up on branch `0_0_0` should you want a copy.

# ABOUT

Junos console/bootstrap New-Out-Of-Box (NOOB) configuration automation. 

There are times when you MUST console into a Junos device to perform the NOOB configuration.  Generally this configuration is the bare minimum in takes to:

  * set the root password
  * set the host-name
  * set the management ipaddr
  * enable ssh and optionally NETCONF

The general use-case:

The `netconify` utility automatically performs this configuration by logging into the serial console, extracting information from the device, and using it to template build a configuration file, and load the result into the device.  The templates are stored in `/etc/netconify/skel` and the device variables for each of the named devices are stored in `/etc/netconify/hosts`.  There are some samples installed by this module.

# USAGE

````
usage: netconify [-h] [-i INVENTORY] [-m EXPLICIT_MODEL] [-j EXPLICIT_CONF]
                 [--qfx-node] [--qfx-switch] [--dry-run] [--no-save] [-F]
                 [-C PREFIX] [-S [SAVEDIR]] [-p PORT] [-b BAUD] [-t TELNET]
                 [-u USER] [-P PASSWD] [-k]
                 [name]

positional arguments:
  name                  name of Junos NOOB device

optional arguments:
  -h, --help            show this help message and exit
  -i INVENTORY, --inventory INVENTORY
                        inventory file of named NOOB devices and variables

DEVICE controls:
  -m EXPLICIT_MODEL, --model EXPLICIT_MODEL
                        EXPLICIT: Junos device model, identifies file in
                        <prefix>/skel
  -j EXPLICIT_CONF, --conf EXPLICIT_CONF
                        EXPLICIT: Junos NOOB configuration file
  --qfx-node            Set QFX device into "node" mode
  --qfx-switch          Set QFX device into "switch" mode
  --srx_cluster REQUEST_SRX_CLUSTER
                        cluster_id,node ... Invoke cluster on SRX device and
                        reboot
  --srx_cluster_disable
                        Disable cluster mode on SRX device and reboot

MODE controls:
  --dry-run             dry-run builds the config only
  --no-save             Prevent files from begin saved into --savedir
  -F, --facts           Only gather facts and save them into --savedir

DIR controls:
  -C PREFIX, --confdir PREFIX
                        override path to etc directory configuration files
  -S [SAVEDIR], --savedir [SAVEDIR]
                        Files are saved into this directory, CWD by default

TTY controls:
  -p PORT, --port PORT  serial port device
  -b BAUD, --baud BAUD  serial port baud rate
  -t TELNET, --telnet TELNET
                        telnet/terminal server, <host>:<port>

LOGIN controls:
  -u USER, --user USER  login user name, defaults to "root"
  -P PASSWD, --passwd PASSWD
                        login user password, *empty* for NOOB
  -k                    prompt for user password
````

# EXAMPLE

Junos NOOB devices can netconified:

````
unix> netconify demosrx
````

Where `demosrx` is the name identified in the `/etc/netconify/hosts` file.  You can omit the name if your configuration files are static; i.e. are not templates with variables.

The NOOB conf file is selected from `/etc/netconify/skel` by the model of the device.  So if `demosrx` was an SRX210H device, the output of the netconify would look like the following.  I also included the command option to save a copy of the auto-generated config file.

````
[jeremy@linux]$ netconify demosrx --savedir . 
TTY:login:connecting to serial port ...
TTY:login:logging in ...
TTY:login:starting NETCONF
CMD:conf:building from: /etc/netconify/skel/SRX210H.conf
CMD:conf:saving: ./demosrx.conf
CMD:conf:loading into device ...
CMD:conf:commit ... please be patient
TTY:logout:logging out ...
````

### Static NOOB files

If your NOOB.conf files do not have any variables, i.e. static, then you do not necessarily need to provide the <name> argument; since there is no need to do <namevars> rendering.  For these use cases, you can use netconify with no parameters:

````
[jeremy@linux]$ netconify
````
The device facts will be used to determine the model information, and from there, the correct NOOB.conf file will be selected and applied.
# INSTALLATION
_not in PyPi yet_

git clone this repo and then use `python setup.py install` to install.  

# DEPENDENCIES

This has been tested with python 2.7.  The required modules are defined in `setup.py`.

# WORK IN PROGRESS

This is still a work in progress, but it is far enough along that you can start trying it out.  If you have any questions, please open an issue against the repo.  Thank you.
