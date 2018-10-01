"""
   dummy implementation allows executing dummy payload and validate input/templates processing
"""

import random

from net.grinder.script.Grinder import grinder

from core import core
from corelibs.coreGrinder  import CoreGrinder


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()


class dummy(core):
 
    
    def __init__(self,_dataFilePath, _templateFilePath):    
        core.__init__(self, _dataFilePath, _templateFilePath)
        self.min_random=properties.getInt('dummy.sleep.min',0)
        self.max_random=properties.getInt('dummy.sleep.max',0)
        if self.min_random>self.max_random:
            self.error('Parameter dummy.sleep.min [%d] and dummy.sleep.max [%d] are not consistent ! ' % (self.min_random,self.max_random))
            raise
        self.sleep=True if self.min_random>0 and self.max_random>0 else False
            

       
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: dummy.grindertool 1.3 2011/06/15 15:52:15CEST omerlin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    
    def sendData(self,**args):
        response=''
        delay=0
        # case : we have a template
        if isinstance(args['data'],str):
            response=args['data']
            config = self.setProperties(args['data'])
            delay = config.get('response0.delay_ms') or None
        # case : we don't have a template, so we have a dictionary
        else:
            response=str(args['data'])
            
        liResp = {'httpStatCode':'200',
                  'responseText':response,
                  'message':response,
                  'errorCode':200 }
        
        
        # Ok, we add also the context for testing
        liResp.update(args['context'])
          
        logger.debug('response: %s' % (liResp))
        
        if self.sleep:
            grinder.sleep(random.randint(self.min_random,self.max_random))

                                                     
        return liResp       

    

