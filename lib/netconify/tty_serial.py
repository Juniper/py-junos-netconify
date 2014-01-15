import serial
import re
from time import sleep
from datetime import datetime, timedelta

from .tty_terminal import Terminal

##### -------------------------------------------------------------------------
##### Terminal connection over SERIAL CONSOLE
##### -------------------------------------------------------------------------

class Serial(Terminal):
  def __init__(self, port='/dev/ttyUSB0', **kvargs):
    """
    :port:
      the serial port, defaults to USB0 since this
    """
    Terminal.__init__(self, port, **kvargs)

  def _tty_dev_init(self, port, kvargs):
    # setup the serial port, but defer open to :login():
    self._ser = serial.Serial()    
    self._ser.port = port
    self._ser.timeout = kvargs.get('timeout', self.TIMEOUT)

  def _tty_dev_open(self):
    self._ser.open()    

  def _tty_dev_close(self):
    self._ser.write('exit\n')
    self._ser.flush()
    self._ser.close()

  def _tty_dev_write(self,content):
    """ write the :context: to the serial port and then immediately flush """
    self._ser.write(content+'\n')
    self._ser.flush()

  def _tty_dev_rawwrite(self,content):
    self._ser.write(content)

  def _tty_dev_flush(self):
    self._ser.flush()        

  def _tty_dev_read(self):
    return self._ser.readline()    

  def write(self, content):
    self._tty_dev_write(content)

  def read(self, expect):
    """
    reads text from the serial console (using readline) until
    a match is found against the :expect: regular-expression object.
    When a match is found, return a tuple(<text>,<found>) where
    <text> is the complete text and <found> is the name of the 
    regular-expression group. If a timeout occurs, then return 
    the tuple(None,None).
    """
    rxb = ''
    mark_start = datetime.now()
    mark_end = mark_start + timedelta(seconds=self.EXPECT_TIMEOUT)

    while datetime.now() < mark_end:
      sleep(0.1)                          # do not remove
      line = self._ser.readline()
      if not line: continue
      rxb += line
      found = expect.search( rxb ) 
      if found is not None: break         # done reading
    else:
      # exceeded the while loop timeout
      return (None,None)

    return (rxb, found.lastgroup)    
