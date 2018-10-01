"""
   dummy implementation allows executing dummy payload and validate input/templates processing
"""

import random
import time
from net.grinder.script.Grinder import grinder

from dummy import dummy
from corelibs.coreGrinder  import CoreGrinder
from corelibs.configuration import Configuration

properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()

reporter=Configuration.getClientReporter()

class report(dummy):
 
    
    def __init__(self,_dataFilePath, _templateFilePath):    
        dummy.__init__(self, _dataFilePath, _templateFilePath)
       
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: dummy.grindertool 1.3 2011/06/15 15:52:15CEST omerlin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    
    def sendData(self,**args):
        if Configuration.use_reporter:
           Configuration.getClientReporter().setTime1(str(time.time()).split('.')[0], 'reporting_is_the_key')
           try:
              Configuration.getClientReporter().customMethod('sending custom probe!')
           except AttributeError, e:
              logger.warn('%s Reporter %s Error[%s]' % (self.__class__.__name__, Configuration.getClientReporter().__class__.__name__, e))
        return dummy.sendData(self,**args)
