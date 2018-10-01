"""
http.grindertool 
Simple http implementation
"""


from StringIO import StringIO
from java.util.regex import Pattern
import sys

from http import http

from corelibs.coreGrinder  import CoreGrinder
logger=CoreGrinder.getLogger()

#--------------------------------------------------
class soap(http):
 
    
    def __init__(self,_dataFilePath, _templateFilePath):    
        http.__init__(self, _dataFilePath, _templateFilePath)

       
    def setProperties(self, configuration):
        '''
           overload the corelibs::setProperties() - It's just for readability 
           otherwise SOAP text must be set on only one line
        '''
        
        if logger.isDebugEnabled(): 
            foo=sys._getframe(0).f_code.co_name
            logger.debug('DEBUG. Function=%s.%s' % (self.__class__.__name__,foo))
         
        objFile = StringIO(configuration)
        reg_param=Pattern.compile(r'^\s*([A-Za-z0-9\.\_]+)\s*=\s*(.*)$')
        props={}
        (value,param,addStr)=('','','')
        for line in objFile.readlines():
            
            #ignore empty string & commentaries
            if line.strip()=='#' or (not line.strip()):
                continue
        
            res = reg_param.matcher(line)
            if res.find():
                if value:
                    props[param]=value
                param,value = res.group(1),res.group(2)
                addStr='\n'
            else:  
                value=value+addStr+line
                addStr=''
        if value:
            props[param]=value
        
        objFile.close()
        
        
        return props

