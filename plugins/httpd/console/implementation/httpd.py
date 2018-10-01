"""
   dummy implementation allows executing dummy payload and validate input/templates processing
"""

import random
import fakeHttpd

from net.grinder.script.Grinder import grinder

from core import core
from corelibs.toolbox import CoreGrinder


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()


class httpd(core):
 
    
    def __init__(self,_dataFilePath, _templateFilePath):    
        core.__init__(self, _dataFilePath, _templateFilePath)
       
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: dummy.grindertool 1.3 2011/06/15 15:52:15CEST omerlin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    
    def sendData(self,**args):
        response=''
        delay=0
        logger.info('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        data = args['data']
        logger.info(data)
        config = self.setProperties(args['data'])
        print config
        port = config.get('request0.port') or 8008
        body = config.get('request0.body')
        status = config.get('request0.statuscode') or 200
        ct = config.get('request0.content_type') or 'Application/xml'
        print config.get('request0.timeout')
        timeout = config.get('request0.timeout') or 5
         
        logger.info(port)
        logger.info(body)
        # case : we have a template
        logger.info("We have a template")
        #rq = fakeHttpd.wait_for_request(8888,'<xml></xml>')
        #rq = fakeHttpd.wait_for_request(int(port),body,timeout=1)
        rq = fakeHttpd.wait_for_request(int(port),body,int(status),ct,int(timeout))
        #    delay = config.get('response0.delay_ms') or None
        
        if rq is None:
           logger.error("No request received before the timeout")
           liResp = {'httpStatCode':'666'}
        else:  
           liResp = {'httpStatCode':'200','responseText':rq,'message':rq,'errorCode':200 }
        logger.debug('response: %s' % (liResp))
        
                                                     
        return liResp       

    

