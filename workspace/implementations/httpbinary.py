"""
httpbinay.grindertool 
       Designed to manage HTTP binary download
"""

import jarray
from java.io import BufferedInputStream
from java.lang import NoClassDefFoundError

from net.grinder.script.Grinder import grinder

from http import http


# Just to be able to test in standalone mode without having grinder runtime
try:
    from net.grinder.plugin.http import HTTPRequest


    #
    class BinaryHTTPRequest(HTTPRequest):
        '''
          A subclass that rewrite the response processing
        '''
        def processResponse(self, response):
    
            #threadContext = HTTPPluginControl.getThreadHTTPClientContext()
            #threadContext.resumeClock()
            
            # We just want to read data flow - so we can scale
            bodyLength = 0
            bin = BufferedInputStream(response.getInputStream())
            buf = jarray.zeros(8192,'b')
            lenBuf = 0
            while lenBuf != -1 :
                lenBuf = bin.read(buf)
                bodyLength += lenBuf  
            bin.close()
            grinder.getLogger().output("INFO: Download of %d bytes finished" % (bodyLength))
            
            #threadContext.pauseClock();
    
            # Update statistics with body size
            testStatistics = grinder.getStatistics()
            if (testStatistics.isTestInProgress()):
                testStatistics.getForCurrentTest().addLong(
                        "httpplugin.responseLength",
                        bodyLength);
        
    class httpbinary(http):
     
        SETCOOKIE      = 'Set-Cookie'
        COOKIE         = 'Cookie'
        
        def __init__(self,_dataFilePath, _templateFilePath):       
            http.__init__(self, _dataFilePath, _templateFilePath)  
            self.validateStatus=False
            self.post_operation=False        
           
        def version(self):
            ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
            and concatenate the two together to create a version string
            return the release string'''
            setVersion = '$Header: httpbinary.grindertool 1.2 2010/11/09 15:50:25CET omerlin Exp  $'.split( )[1:3]
            return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'
           
    
        def processResponse(self, response):     
            #
            # retrieve the necessary data (status code, errorCode, message)
            #
            liResp = {}
            liResp['httpStatCode'] = response.getStatusCode()
            liResp['message']   = str(response.getReasonLine())
            liResp['errorCode'] = ''
                     
            for name in response.listHeaders():
                value = response.getHeader(name)
                liResp[name] = value
                                                 
            return liResp
            
        def callHTTP(self, uri, body, http_headers):
            self.log("URI : [%s] Executing Binary DOWNLOAD" % (uri), 'INFO')            
            response = BinaryHTTPRequest().GET(uri, None ,http_headers)               
            return response    
    
    
except NoClassDefFoundError,e:
    pass






