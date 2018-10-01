'''
Created on Jan 18, 2012

@author: omerlin
'''
import os

from core import core
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()

loadedFile = {}
class command(core):
    '''
        A generic shell command executor
    '''
    def __init__(self,_dataFilePath, _templateFilePath):
        core.__init__(self, _dataFilePath, _templateFilePath)        
        self.memorizedData = {}
        self.dataFilePath = _dataFilePath
        self.templateFilePath = _templateFilePath
        self.shellCommand=self.properties.get('shellCommand') or None
        if not self.shellCommand:
            self.error('Parameter shellCommand is REQUIRED in the properties file !!!')
            raise

    def callCommand(self,str2send):
        """
           - add store to the client
           - add synchronization data
           - launch synchronization 
        """
        self.debug('callCommand begin' )
        
        # Read the template configuration
        config = self.setProperties(str2send)
        
        # should contains this key
        request = config.get('request0.body')
        
        fields = request.split(';')        
        command=self.shellCommand+ ''.join([' %s' % (k)  for k in fields])
        
        print 'Executing Command:'+command
        ret=os.system(command)
        print 'INFO: return code=%d' % (ret)
        
        liResp = {}
        liResp['httpStatCode'] = '200'
        liResp['responseText'] = 'command'
        liResp['message']   = 'command'
        liResp['errorCode'] = ''
        
        delay = config.get("response0.delay_ms") or None
        if delay:
            grinder.sleep(int(delay)) 

        self.debug('callCommand end' )

        return liResp       
           
            
    def sendData(self, **args ):
        return self.callCommand(args['data'])    

    
