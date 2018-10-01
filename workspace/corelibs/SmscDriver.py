'''
Created on 23 sept. 2014

@author: csahli
'''

from _threading import Condition
from java.lang import Runnable, Thread
import time

from com.gemplus.smscpdu.smpp import SMPPData
from com.gemplus.smscpdu.smpp import SMPPSubmit
from com.gemplus.smscsimulator import SmscServer
from com.gemplus.smstools.gsm0340 import Data0348WithMsisdn
from com.gemplus.tools.smsctoolkit.clientapi import DataFlowNodeListener

from corelibs.contextIdentifier import ContextIdentifier
from corelibs.coreGrinder  import CoreGrinder
from corelibs.grinderQueue import GrinderQueue
from corelibs.token import SMPPToken


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


FROM_OTA_INPUT=0
FROM_PREVIOUS_INPUT=1

TO_OTA_OUTPUT=0
TO_NEXT_OUTPUT=1


class _SMSCDriver ( DataFlowNodeListener,  Runnable):
    
    connected=False
    # waiting Mode
    waitingMode=False
    if properties:
        waitingMode = properties.getBoolean('waiting_mode', False)  
    
    def __init__ (self,p_profilePath):
        self.m_profilePath = p_profilePath
        try :       
            self.m_server = SmscServer()
            self.m_server.loadProfile(self.m_profilePath)            
            self.tcpPlugin = self.m_server.getNodeFromQualifiedName("TCP")            
            
            self.dataFlowNodeWithListener = self.m_server.getNodeFromQualifiedName("Listener")            
            if(self.dataFlowNodeWithListener != None):
                self.dataFlowNodeWithListener.setListener(self)
            
            logger.debug('SMSCDriver initialized')
        except Exception, e:
            logger.error('SMSCDriver initialization failed, reason = %s' % (e))
            raise                  

    def waitUntilTCPConnected(self,tcpPlugin):
        tcpPlugin.waitUntilConnected()
    
    def run(self):
        try :
            self.m_server.work()
            logger.debug("... SMSC server started")
            time.sleep(3)
            logger.debug("... SMSC server waiting after OTA connection")
            self.tcpPlugin.waitUntilConnected()
            logger.debug('... SMSC server connected')
            self.__class__.connected=True

        except Exception, x:
            logger.error('_SMSCDriver, got an exception: %s' % (str(x)))
            raise '_SMSCDriver, got an exception: %s' % (str(x))
            
    def isConnected(self):
        return self.__class__.connected
    
    def shutdown(self):
        self.m_server.shutdown()

    def stop(self):
        self.m_server.shutdown()
        self.m_server = None

    def send(self,data):
        self.dataFlowNodeWithListener.send(data, 0)
    
    def __interpretedToDict(self, s):
        s=s.replace('{','').replace('}','')
        d={}
        for k in s.replace('\n\n','').split('\n\t')[1:]:
            name,value=k.replace('(','').replace(')','').replace(' : ',':').split(':',1)
            d[name.replace(' ','_').lower()]=value.strip()
        return d
    def __toString(self,d):
        return ','.join(['%s=%s'%(k,v) for k,v in d.iteritems()])
    
    def _data0348toInterpretedString(self, data0348):
        d={}
        d['cntr']=data0348.getCNTRAsString()
        d['kic']=data0348.getKIcAsString()
        d['kid']=data0348.getKIDAsString()
        d['secureddata']=data0348.getSecuredDataAsString()
        d['user_data_binary']=d['secureddata']
        d['spi']=data0348.getSPIAsString()
        d['tar']=data0348.getTARAsString()
        d['originatingaddress']=data0348.getOriginatingAddress().getStringAddress()
        d['porrequestvalue']=str(data0348.getPoRRequestValue())
        d['statuscode']=str(data0348.getStatusCode()) 
        return d
    
    def handleRequestFromInput(self, inputNumber, data):
        logger.debug('[inputNumber=%d][data=%s][type=%s]' % (inputNumber, data, type(data)))      
        try :    
            
            if inputNumber == FROM_OTA_INPUT:
                # MT 
                dict_data={}
                msisdn=None
                if (isinstance(data,SMPPSubmit) or isinstance(data,SMPPData)):
                    logger.info  ("SMPP Submit processing")                                       
                    msisdn=data.getDestinationAddress().getStringAddress()  
                    dict_interpreted=self.__interpretedToDict(data.toInterpretedString())
                    dict_data.update(dict_interpreted)
                    dict_data['interpretedData']=self.__toString(dict_interpreted)
                
                elif isinstance(data,Data0348WithMsisdn):
                    logger.info  ("SMPP O348Data processing")                                       
                    msisdn=data.getDestinationAddress().getStringAddress() 
                    dict_data=self._data0348toInterpretedString(data)
                
                if msisdn:
                    if self.__class__.waitingMode:
                        contextToken = SMPPToken('msisdn', msisdn, dict_data)
                        logger.debug('Adding a SMPPToken %s to the FIFO queue [context=waitingMode]' % (contextToken))
                        GrinderQueue.put(  contextToken )
                    else:
                        # Hardening in case callback comes to fast
                        # This is probably useless since we use now an optimistic lock for asynchronous calls
                        retryCount=0
                        foundInContext=False
                        while ( retryCount<5):
                            if ContextIdentifier.exists('msisdn',msisdn):
                                foundInContext=True
                                break
                            # Sleep 100 ms
                            Thread.sleep(100)
                            retryCount+=1
                            if logger.isTraceEnabled():
                                logger.trace('Tried to find msisdn=%s in context - try=%d/5' % (msisdn, retryCount))
                        if foundInContext:
                            contextToken = SMPPToken('msisdn', msisdn, dict_data)
                            logger.debug('Adding a SMPPToken %s to the FIFO queue [context=normal Async callback]' % (contextToken))
                            GrinderQueue.put(  contextToken )
                        else:
                            logger.error('[state=unknownEventReceived] SMSCDriver - IGNORED Unknown EVENT [contextKey=msisdn] [value=%s] received' % (msisdn))

                else:
                    logger.error('STRANGE ERROR - got MT smpp message without msisdn, please review the use case !')

                logger.debug('>>> FROM_OTA >>> dataFlowNodeWithListener.send')   
                self.dataFlowNodeWithListener.send(data, TO_NEXT_OUTPUT)

            if inputNumber == FROM_PREVIOUS_INPUT:
                logger.debug('<<< TO_OTA <<< dataFlowNodeWithListener.send')   
                self.dataFlowNodeWithListener.send(data, TO_OTA_OUTPUT)
            
                
        except Exception, ex:
            logger.error ( 'handleRequestFromInput() : Oops ... reason: %s' % (ex))
            raise
            
    def reStart(self):
        if( self.m_server != None ):
            logger.error("The server is not null. Cannot restart SMSC server !")
            raise Exception("The server is not null. Cannot restart SMSC server !")
        if( self.m_profilePath == None ):
            logger.error("The profile path is not defined. Cannot restart SMSC Server !")
            raise Exception("The profile path is not defined. Cannot restart SMSC Server !")
        self.initialize(self.m_profilePath)

        try:
            self.startSmsc()
        except Exception:
            raise


class SMSCDriver:
    cv_smpp=Condition()
    smscDriver=None
    smscDriverThread=None
    started=False
    
    def __init__(self, profilePath):
        self.__class__.cv_smpp.acquire()
        if self.__class__.smscDriver == None:
            try:
                self.__class__.smscDriver=_SMSCDriver(profilePath)
                self.__class__.smscDriverThread = Thread(self.__class__.smscDriver, "SMSCDriver")
#                 self.__class__.smscDriverThread.setDaemon(True)
            except Exception,ex:
                logger.error( 'Error loading SMSC Profile : %s, reason: %s' % (profilePath, ex))
                raise
            logger.debug( 'SMSC Server starting')
            self.__class__.smscDriverThread.start()
            logger.info(  'SMSC Server started in the thread %s' % (self.__class__.smscDriverThread.getName()))
            self.__class__.started=True
        self.__class__.cv_smpp.release()
        
    def stop(self):
        self.__class__.smscDriver.stop()
        self.__class__.smscDriverThread.stop()

    @classmethod
    def isConnected(cls):
        return cls.smscDriver.isConnected()

    @classmethod
    def isStarted(cls):
        return cls.started
    
    @classmethod
    def getSmscDriver(cls):
        return cls.smscDriver