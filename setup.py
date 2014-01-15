import os, sys
from glob import glob
from setuptools import setup, find_packages

requirements = [ 'jinja2','pyserial','lxml' ]

setup(
    name = "netconify",
    version = "0.0.1",
    author = "Jeremy Schulman",
    author_email = "nwkautomaniac@gmain.com",
    description = ( "Junos console/bootstrap automation"),
    license = "Apache 2.0",
    keywords = "Junos NETCONF NOOB automation networking",
    url = "http://www.github.com/jeremyschulman/py-junos-netconify",
    install_requires=requirements,
    packages=find_packages('lib'),
    package_dir={'':'lib'},
    scripts=['tools/netconify'],
    data_files=[
      ('/etc/netconify/skel', glob('etc/skel/*.conf')),
      ('/etc/netconify', ['etc/hosts'])
    ]
)
