import jnpr.netconify

tty = jnpr.netconify.Serial(user='root', passwd='juniper123')
tty.login()

# ... do stuff ...

# tty.logout()
