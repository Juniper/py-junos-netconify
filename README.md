# ABOUT

Junos console/bootstrap New-Out-Of-Box (NOOB) configuration automation. 

There are times when you MUST console into a Junos device to perform the NOOB configuration.  Generally this configuration is the bare minimum in takes to:

  * set the root password
  * set the host-name
  * set the management ipaddr
  * enable ssh and optionally NETCONF

The general use-case:

The `netconify` utility automatically performs this configuration by logging into the serial console, extracting information from the device, and using it to template build a configuration file.  The templates are stored in `/etc/netconify/skel` and the variables for each of the named devices is stored in `/etc/netconify/hosts`.  There are some samples installed by this modu

# USAGE

````
usage: netconify [-h] [--prefix PREFIX] [-i INVENTORY] [--dry-run]
                 [--savedir SAVEDIR] [-M EXPLICIT_MODEL] [-C EXPLICIT_CONF]
                 [-P PORT] [--baud BAUD] [-u USER] [-p PASSWD] [-k]
                 [name]

positional arguments:
  name                  name of Junos NOOB device

optional arguments:
  -h, --help            show this help message and exit
  --prefix PREFIX       path to etc files
  -i INVENTORY, --inventory INVENTORY
                        inventory file of named NOOB devices and variables
  --dry-run             dry-run builds the config only
  --savedir SAVEDIR     save a copy the NOOB conf file into this directory
  -M EXPLICIT_MODEL, --model EXPLICIT_MODEL
                        EXPLICIT: Junos device model, conf from skel dir
  -C EXPLICIT_CONF, --conf EXPLICIT_CONF
                        EXPLICIT: Junos NOOB conf file
  -P PORT, --port PORT  serial port device
  --baud BAUD           serial port baud rate
  -u USER, --user USER  login user name
  -p PASSWD, --passwd PASSWD
                        login user password, alternatively use -k option to
                        prompt
  -k                    prompt for password
````

