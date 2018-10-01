import base64
import datetime
import random

from corelibs.coreGrinder  import CoreGrinder


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()

class Utils():

    def greater(self, val1, val2):
        return float(val1)>float(val2)
    def greaterOrEqual(self, val1, val2):
        return float(val1)>=float(val2)
    def smaller(self, val1, val2):
        return float(val1)<float(val2)
    def smallerOrEqual(self, val1, val2):
        return float(val1)<=float(val2)

    def true(self):
        return True

    def dummy(self, val):
        return val

    def get_locale_tz_timestamp(self):
        return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    def get_utc_tz_timestamp(self):
        return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def swap(self, msisdn):
        '''
           swap digits pair  
           :param msisdn:
        '''
        return self.swapAlt(msisdn)

    def swapAlt(self, line):
        '''
          A pythonic version of swap()
        :param line:
        '''
        return ''.join([ '%s%s' % (line[i+1:i+2],line[i:i+1]) for i in range(0, len(line)) if i%2==0])

    def fromIccid(self, iccid):
        '''
           iccid are on 20 characters
           imsi and imei are 15 characters long
           Identifier of iccid range are on the 4 first characters. (prefix)
        :param iccid:
        :param len:
        '''
        try:
            assert len(iccid) == 20
        except :
            raise SyntaxError( 'Invalid iccid [%s] [len=%d] - must be of length 20' % (iccid,len(iccid)))

        return '%s%s' % (iccid[:4], iccid[-11:]) 

    def fromFixedIccid(self, iccid):
        '''
           iccid are on 20 characters
           imsi and imei are 15 characters long
           Identifier of iccid range are on the 4 first characters. (prefix)
        :param iccid:
        :param len:
        '''
        try:
            assert len(iccid) == 20
        except :
            raise SyntaxError( 'Invalid iccid [%s] [len=%d] - must be of length 20' % (iccid,len(iccid)))

        l=list(iccid[8:15])
        random.shuffle(l)


        return '%s%s' % (iccid[:8], ''.join(l)) 

    
    def randomImei(self, iccid):
        '''
          generate a fake target (random) imei  
        :param imei: input imei
        '''
        l=list(self.fromIccid(iccid))
        random.shuffle(l)
        
        try:
            assert len(l) == 15
        except :
            raise SyntaxError( 'Invalid imei [%s] [len=%d] - must be of length 20' % (''.join(l) ,len(l)))
        
        
        return ''.join(l)    
    
    
    

    def imei_from_sequence(self, iccid, seqid):
        '''
           iccid are on 20 characters
           imsi and imei are 15 characters long
           Identifier of iccid range are on the 2 first characters. (prefix)
           the last part is the diversified one ( the last <len> characters )
           for imei & imsi, it's generally on 13 characters
        :param iccid:
        :param len:
        '''
        try:
            assert len(seqid) == 4
        except :
            raise SyntaxError( 'Invalid sequence id [%s] - must be of length 4' % (seqid))
        
        return '%s%s%s' % (iccid[:2], seqid, iccid[-9:]) 

    def getBasicAuthorization(self, user, password):
        '''
           Asked for Rest implementation. Adding the possibility to encode in base64 basic authentication    
        :param user: username
        :param password: password
        '''
        return base64.b64encode('%s:%s' % (user,password))

    def getProcessNumber(self):
        return str((grinder.processNumber % int(properties.get('grinder.processes')))).zfill(int(properties.get('processNumberPadding')))

instance = Utils()

def getInstance():
    return instance
