import netconify

tty = netconify.Serial(user='root', passwd='juniper123')
tty.login()

# ... do stuff ...

# tty.logout()
