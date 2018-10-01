'''
Created on Sep 30, 2010

@author: omerlin
'''
from StringIO import StringIO
#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder,MySyntaxError
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()
#----------------------------------------------------------------------

# Get the log level
logThreshold='ERROR'
if properties:
    logThreshold=(properties.get('logLevel') or '').upper() or 'ERROR'


class core(object):
    levelDict = {'FINEST':0, 'DEBUG':5,'INFO':10,'CONSOLE':10, 'WARNING':15, 'ERROR':20,'FATAL':30}

    dictLogger = { 'FINEST':logger.debug, 'TRACE':logger.debug, 
                   'DEBUG':logger.debug, 'INFO':logger.info, 'CONSOLE':logger.info,
                   'WARNING':logger.warn, 'ERROR':logger.error, 'FATAL':logger.error}
    
    def __init__(self,_dataFilePath, _templateFilePath):

        self.dataFilePath = _dataFilePath
        self.templateFilePath = _templateFilePath
        
        self.URI = ''
        ## Have a single runID base on process.run.test_thread.line 
        self.fullRunID = ''
        self.processID = ''
        self.threadID = ''
        self.runID = ''
        self.loopID = ''
        self.lineID = ''        

#         logger.debug('displayReadResponse <'+str(self.displayReadResponse)+'>')
        self.previousLevel=None
        self.debug_activated = (logThreshold == 'DEBUG')
        self.logger=logger

    def shutdown(self):
        pass
    
    @staticmethod
    def checkRequiredProperty(key):
        if key not in properties:
            raise MySyntaxError('**** required key "%s" **** is not defined !' % (key) )

    def log(self, message, threshold='DEBUG'):
        self.dictLogger[threshold](threshold + ": " + message)

    def isDebugEnabled(self):
        return self.debug_activated
    
    def setDebugEnabled(self):
#         self.previousLevel=logThreshold
        logThreshold='DEBUG'
        self.debug_activated = (logThreshold == 'DEBUG')
        
    def unsetDebugEnabled(self):
        logThreshold=self.previousLevel
        self.previousLevel=None
        self.debug_activated = (logThreshold == 'DEBUG')
    
    def debug(self,message):
        return self.log(message,'DEBUG')
    def info(self,message):
        return self.log(message,'INFO')
    def warn(self,message):
        return self.log(message,'WARNING')

    def error(self,message):
        return self.log(message,'ERROR')
        
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: corelibs.grindertool 1.13 2012/06/05 18:01:22CEST omerlin Exp  $'.split( )[1:3]
        retVal = setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'
        return retVal
        
    def processResponse(self,str2send, mtasResp):
        '''
              Interface to be defined
        @param str2send:
        @param mtasResp:
        '''
        liResp = {}        
        return liResp
    
    @classmethod
    def process_data(cls, data):
        '''
           process_data is for the moment used by asynchronous callback code.
           post-processing of data is only possible by the implementation that knows what to do with the data format gotten.
           :param data: a string data object to be processed by the implementation
        '''
        # nothing here - this is a pure interface
        return data
    
    def sendData(self, **kargs):
        """
        common function called by process() of grindertool.grindertool for each implemented library
        the string to send 
        """
        sResp = self.__class__+'is an abstract class - Not implemented'
        return sResp

    def setProperties(self, configuration):
        
        objFile = StringIO(configuration)
        try:
            configuration = dict()
            lastkey = ''
            for line in objFile.readlines():
                if (line.strip()[0] != '#' ):
                    parts = line.strip().split('=',1)
                    if len(parts) == 2:
                        lastkey = parts[0]
                        configuration[parts[0]] = parts[1]
                    elif len(lastkey) > 0:
                        configuration[lastkey] += '\n'
                        configuration[lastkey] += line.rstrip()
        except ValueError, x:
            raise SyntaxError("failed to split template file!\n%s"%( x))
        
        objFile.close()

        return configuration
        
    
    def getProperties(self):
        """get the host/port/uri & get/post method from the grindertool file
        and insert them into a list
        return the list"""
    
        di = {}                
        return di


    def setFullRunID(self, idStr):
        """
           Have a single runID base on process.run.test_thread.line 
        @param runID
        """
        self.fullRunID = idStr;

    def setProcessID(self, id1):
        """
            part1 of the runID 
        """
        self.processID = id1;

    def setThreadID(self, id2):
        """
            part2 of the runID 
        """
        self.threadID = id2;

    def setRunID(self, id3):
        """
            part3 of the runID
        """
        self.runID = id3;

    def setLoopID(self, id4):
        """
            part(4) of the runID
        """
        self.loopID = id4;

    def setLineID(self, id5):
        """
            part4 or 5 of the runID 
        """
        self.lineID = id5;
        
