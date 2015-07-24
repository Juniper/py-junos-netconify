import os
import sys
from glob import glob
from setuptools import setup, find_packages

requirements = ['pyserial', 'lxml']

setup(
    name="junos-netconify",
    version="1.0.1",
    author="Jeremy Schulman",
    author_email="jnpr-community-netdev@juniper.net",
    description=("Junos console/bootstrap automation"),
    license="Apache 2.0",
    keywords="Junos NETCONF basic CONSOLE automation",
    url="http://www.github.com/Juniper/py-junos-netconify",
    install_requires=requirements,
    packages=find_packages('lib'),
    package_dir={'': 'lib'},
    scripts=['tools/netconify'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Other Scripting Engines',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
        'Topic :: Text Processing :: Markup :: XML'
    ],
)
