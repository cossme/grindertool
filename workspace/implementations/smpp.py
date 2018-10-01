'''
Created on 23 sept. 2014

@author: csahli
'''

from java.lang import  Byte
from java.util import Date
from threading import Condition
from com.gemplus.smscpdu.smpp import SMPPProtocol
from com.gemplus.smstools.gsm0340 import GSMAddress
from corelibs.SmscDriver import SMSCDriver

from core import core
#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


class smpp(core):
    
    cv_send=Condition()
    
    def __init__ (self, _dataFilePath, _templateFilePath):
        pass

        
    def sendsmpp(self,data):
        
        # Add control of keys
        
        da = data['destinationAddress'] 
        oa = data['originatingAddress'] 
        userData = data['userData']
       
        originatingAddress = GSMAddress(oa)
        destinationAddress = GSMAddress(da)
        myProtocol = SMPPProtocol()
        protocolIdentifier = Byte('7')
        serviceCenterTimeStamp = Date()
        replyPathIndication = False
        udhIndication = True
        dataCodingScheme = Byte('0')
        isBinaryUserData = True

        myDeliver = myProtocol.createDeliver(destinationAddress,
                                             originatingAddress,
                                             protocolIdentifier,
                                             serviceCenterTimeStamp,
                                             userData,
                                             replyPathIndication,
                                             udhIndication,
                                             dataCodingScheme,
                                             isBinaryUserData)
        resp={}
        resp['errorCode']=200     
        resp['responseText']=myDeliver.toInterpretedString()
        logger.debug('>>>> %s' % (resp['responseText'])) 

        try:
            self.__class__.cv_send.acquire()
            smsc=SMSCDriver.getSmscDriver()
            if smsc:
                smsc.send(myDeliver)
            else:
                raise SyntaxError('SMSCDriver has not been started !!')
            self.__class__.cv_send.release()
        except Exception, ex:
            errMsg="Unable to send data, reason: %s" % (ex)
            logger.error(errMsg)
            resp['errorCode']=500
            resp['responseText']=errMsg
        
        return resp 


    def sendData(self, **args):
        return self.sendsmpp(args['data'])    
