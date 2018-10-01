"""
   dummy implementation allows executing dummy payload and validate input/templates processing
"""

from net.grinder.script.Grinder import grinder
logger=grinder.logger

class dummy_xml:
    
    def __init__(self,arg0=None,arg1=None):
        pass
                   
    def sendData(self,**args):
        
        d=args['data']

        # key data is to simulate the data key entry of async callback        
        if 'data' in d:
            msg=d['data']
        else:
            msg=str(d)
            
        liResp = {'httpStatCode':'200',
                  'responseText':msg,
                  'errorCode':'200' }
                                            
        return liResp