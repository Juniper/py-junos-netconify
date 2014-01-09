from jnpr.netconify import  *

tty = netconify(user='root', passwd='juniper123')
tty.login()

# ... do stuff ...

# tty.logout()
