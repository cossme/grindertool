'''
Created on Aug 3, 2012

@author: omerlin
'''
import StringIO
import gzip
from java.util.regex import Pattern
import os
import random
from threading import Condition
import time
import zlib

from net.grinder.script.Grinder import grinder
from net.sf.json import JSONSerializer, JSONException, JSONArray, JSONObject


version=1.4
def getRequestId( threadNumber, runNumber) : 
    return '%s%s%s'%( str(time.time()).replace('.',''),threadNumber,runNumber)


def strTime():
    return  str(time.time()).replace('.','')[:-2]

def timeMilli():
    return  strTime()+'0'


class MyShareBox():
    def __init__(self, fileids, contactids):
        self.fileids = fileids
        self.contactids = contactids

        
class MyFile:
    def __init__(self, dirImage, file1):
        self.directory=dirImage
        self.filename=file1
        fullname='%s/%s' % (self.directory, file1)
        self.size=os.stat(fullname).st_size
        self.bytes=open(fullname, 'rb').read()
        

def loadAllFiles(properties, myProperty):
    try:
        dirImage = properties.get(myProperty) 
        os.listdir(dirImage)
    except:
        print 'Error with property %s - either missing OR directory %s not found' % (myProperty, dirImage)  
        raise        
    return [MyFile(dirImage,file1) for file1 in os.listdir(dirImage)]

    
def inMemoryMultipartGen( fileObj, csrfToken, diversifyRate, boundery_parameter=None):
    '''
       For project CnS
       Generate bytes data representing a photo binary file (filee1=full path of a file) 
       with the multipart data (csrfToken)
       Note : the boundery may or not be a parameter
    '''
    boundery = boundery_parameter or strTime()
    start_part=('''-----------------------------%s\r\nContent-Disposition: form-data; name="fileField"; filename="%s"\r\nContent-Type: image/jpeg\r\n\r\n''' % (boundery,fileObj.filename)).encode('ascii')
    end_part=('''\r\n-----------------------------%s\r\nContent-Disposition: form-data; name="csrfToken"\r\n\r\n%s\r\n-----------------------------%s--\r\n''' % (boundery, csrfToken, boundery)).encode('ascii')  
    
#     outdata=StringIO.StringIO()
#     outdata.write(start_part)
#     if random.randint(1,diversifyRate) == 1:
#         outdata.write(fileObj.bytes)
#     else:
#         pos=fileObj.size/2
#         outdata.write(fileObj.bytes[:pos-8])
#         outdata.write(''.join([random.choice('?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopkrstuvwxyz0123456789') for i in range(15)]))
#         outdata.write(fileObj.bytes[pos+8:])
#     outdata.write(end_part)
# 
#     myBytes=outdata.getvalue()
#     outdata.close()

    myBytes = start_part
    if random.randint(1,diversifyRate) == 1:
        myBytes += fileObj.bytes
    else:
        pos=fileObj.size/2
        myBytes += fileObj.bytes[:pos-8]
        myBytes += ''.join([random.choice('?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopkrstuvwxyz0123456789') for i in range(16)])
        myBytes += fileObj.bytes[pos+8:]
    myBytes += end_part

    return myBytes

def multipartGen( dir1, filename, csrfToken,boundery_parameter=None):
    '''
       For project CnS
       Generate bytes data representing a photo binary file (filee1=full path of a file) 
       with the multipart data (csrfToken)
       Note : the boundery may or not be a parameter
    '''
    boundery = boundery_parameter or strTime()
    
    start_part=('''-----------------------------%s\r\nContent-Disposition: form-data; name="fileField"; filename="%s"\r\nContent-Type: image/jpeg\r\n\r\n''' % (boundery,filename)).encode('ascii')
    end_part=('''\r\n-----------------------------%s\r\nContent-Disposition: form-data; name="csrfToken"\r\n\r\n%s\r\n-----------------------------%s--\r\n''' % (boundery, csrfToken, boundery)).encode('ascii')  
    
    outdata=StringIO.StringIO()
    outdata.write(start_part)
    outdata.write(open('%s/%s' % (dir1,filename),'rb').read())
    outdata.write(end_part)

    bytes=outdata.getvalue()
    outdata.close()
    return bytes


def AndroidMultipartGen( fileObj, diversifyRate, bounderyparam):
    '''
    MultiPart generation fro Android Client
    '''
    boundery = bounderyparam
    start_part=('''-----------------------------%s\r\nContent-Disposition: form-data; name="filefield"; filename="%s"\r\nContent-Type: application/octet-stream\r\nContent-Transfer-Encoding: binary\r\n\r\n''' % (boundery,fileObj.filename)).encode('ascii')
    end_part=('''\r\n-----------------------------%s--\r\n''' % (boundery)).encode('ascii')  

    myBytes = start_part
    if random.randint(1,diversifyRate) == 1:
        myBytes += fileObj.bytes
    else:
        pos=fileObj.size/2
        myBytes += fileObj.bytes[:pos-8]
        myBytes += ''.join([random.choice('?ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopkrstuvwxyz0123456789') for i in range(16)])
        myBytes += fileObj.bytes[pos+8:]
    myBytes += end_part

    return myBytes



def manageGzipFormat(result):
    '''
       The idea is to convert gzip data at the grinder level to be able to do parsing
       Warning: HTTPResponse return array() signed bytes into getData() call
                to convert to a jython unsigned byte string, we use array().tostring() 
    '''
    try:
        encoding = result.getHeader("Content-Encoding")
    except:
        return result
    #print 'encoding header='+encoding   
    if encoding in ('gzip', 'x-gzip', 'deflate'):
        if encoding == 'deflate':
            decoded_data = StringIO.StringIO(zlib.decompress(result.data.tostring())).read()
        else:
            gzipdata = gzip.GzipFile(fileobj=StringIO.StringIO(result.data.tostring()))
            decoded_data = gzipdata.read()
        return  decoded_data
    return result.text

def oneContactJSON(data):
    datastr=str(data)
    lendata=len(datastr)
    phoneNumber = '+' + datastr
    firstName = 'CnS_F' + datastr
    lastName = 'CnS_' + str(data)
    email = "%s" % (datastr[1:lendata/2] + '@' + datastr[lendata/2:] + '.com')
    myJsonArr1 = JSONArray()
    myJsonObj = JSONObject()
    myJsonObj1 = JSONObject()        
    myJsonObj1.put("type","mobile")
    myJsonObj1.put("phoneNumber",phoneNumber)
    myJsonArr1.add(myJsonObj1) 
    myJsonObj.accumulate("phoneNumbers",myJsonArr1)
    myJsonObj.put("email",email)
    myJsonObj.put("firstName",firstName)
    myJsonObj.put("lastName",lastName)
    myJsonObj.put("pictureId","")
    return myJsonObj
    
def contactsJSON(data,n):
    myJsonArr = JSONArray()
    for i in range(1,n+1):
        myJsonObj = oneContactJSON(data+i)
        myJsonArr.add(myJsonObj)
    fakecontact = '444' + str(random.randint(1000000,9999999))
    myJsonObj = oneContactJSON(fakecontact)
    myJsonArr.add(myJsonObj)
    myStr = '[' + myJsonArr.join(',') + ']'
    return myStr
           
def parseJsonResult(result):
    errorFound=False
    
    json = JSONSerializer.toJSON( manageGzipFormat(result) )
    try:
        iserror = json.getString("iserror")
        if iserror.lower() == 'true':
            errorFound=True     
    except:
        print 'No tag iserror in the text JSON'
        print '%s' % (result.text)
        print '-'*50
        
    if errorFound:
        statistics = grinder.getStatistics().getForCurrentTest()
        statistics.success=0                    

def parseGatekeeper(result):
    accountid=None
    oat=None
    print result.text
    str=unicode(result.text)
    print str
    json = JSONSerializer.toJSON( str )
    data = json.getString("url")
    #{"url":"http://cloudshare/ws/storage.do?method\u003dpostFile\u0026filename\u003d1.bmp\u0026filesize\u003d3078690\u0026copy\u003dtrue\u0026resourceid\u003d00000000000000000000000000000000\u0026format\u003djson2\u0026dc\u003d1355320426936\u0026accountid\u003d502a53da371747e9a002cf7027fb0bd2\u0026oat\u003dc15b3d0d7c64b981975d1f2bd2da3c2ccf60690c","success":true}
    #data='''http://cloudshare/ws/storage.do?method\u003dpostFile\u0026filename\u003d1.bmp\u0026filesize\u003d3078690\u0026copy\u003dtrue\u0026resourceid\u003d00000000000000000000000000000000\u0026format\u003djson2\u0026dc\u003d1355320426936\u0026accountid\u003d502a53da371747e9a002cf7027fb0bd2\u0026oat\u003dc15b3d0d7c64b981975d1f2bd2da3c2ccf60690c'''
    
    hash = dict( [k.split('=') for k in data.split('&')])
    return hash['accountid'],hash['oat'] 

def json_parse_contacts(result):
    filekeys=[]
    #contactids=[]
    json = JSONSerializer.toJSON( manageGzipFormat(result) )
    data = json.getJSONObject("data")
    try:
        json2=JSONSerializer.toJSON( data.getString("contacts") )
        arr = json2.toArray()
        for k in arr:
            filekeys.append(k.getString("filekey"))
            #contactids.append(k.getString("contactid"))
    except JSONException,e:
        print 'WARNING: JSON message for contacts was already retrieved for this session'
        pass
    
    #return filekeys,contactids
    return filekeys

def json_parse_filekeys(result):
    filekeys=[]
    json = JSONSerializer.toJSON( manageGzipFormat(result) )
    data = json.getJSONObject("data")
    json2=JSONSerializer.toJSON( data.getString("contacts") )
    arr = json2.toArray()
    for k in arr:
        filekeys.append(k.getString("filekey"))
    
    return filekeys

def parseJsonTagValue(result, tag): 
    json = JSONSerializer.toJSON( manageGzipFormat(result) )
    try:
        data = json.getJSONObject(tag)
        token = data.getString(tag)
    except:
        token=json.getString(tag)       
    return token


def parseJsonTag(result, maintag="data", tag=''): 
    json = JSONSerializer.toJSON( manageGzipFormat(result) )
    try:
        data = json.getJSONObject(maintag)
        token = data.getString(tag)
    except:
        token=json.getString(tag)       
    return token

def match_regexp(result, regexp_str, opt = 'Pattern.CASE_INSENSITIVE', grp = 1):
    """ Look for an identifier in a text body. The regexp must look for one group """
    # 'SID=(\w+)'
    regExp=Pattern.compile(regexp_str,opt)
    body=manageGzipFormat(result)
    found = regExp.matcher(body)
    if found.find():
        return found.group(grp)
    else:
        raise 'Pattern [%s] NOT found in the text:\n[%s]' % (regexp_str,body)

#======================================================
cv_msisdn= Condition()
debug=False
class msisdnGenerator:

    # Class variable - to share memory
    msisdn=[]
        
    def __init__(self, min_property, max_property):
#    def __init__(self, min_property='min_msisdn', max_property='max_msisdn'):
        ''' 
        '''
        properties=grinder.getProperties()
        self.nbThread=properties.getInt('grinder.threads', 0)
        if self.nbThread<=0:
            raise 'Problem with your grinder.threads parameter definition - Got [%d]' % (self.nbThread)
        self.min_msisdn=properties.getInt(min_property, 0)
        self.max_msisdn=properties.getInt(max_property, 0)
        if not self.min_msisdn or not self.max_msisdn:
            raise 'properties min_msisdn and max_msisdn MUST BE DEFINED in your grinder.properties file'
        self.generation_mode = (properties.get('msisdn_generation') or 'random').upper() 
        if not self.generation_mode in ('RANDOM','SEQUENTIAL','MIXED'):
            raise 'Invalid msisdn generation mode - Found %s - required RANDOM, SEQUENTIAL or MIXED' % (self.generation_mode)
        self.counter=0
        
        
        #
        # Drawback: Great Memory cost but limited to one class variable
        #
        if self.generation_mode == 'RANDOM':
            # We protect this call - only one initialization
            if debug: print 'BEFORE LOCK()'
            cv_msisdn.acquire()
            if len(self.__class__.msisdn)==0:
                if debug: print 'Shuffling MSISDN'
                self.__class__.msisdn = range(self.min_msisdn,self.max_msisdn)
                random.shuffle(self.__class__.msisdn)
                if debug: print 'Shuffling done'
            cv_msisdn.release()
            if debug: print 'len=%d' % (len(self.__class__.msisdn))

    def __repr__(self):
        return 'min=%d,max=%d,nbThreads=%d' % (self.min_msisdn,self.min_msisdn,self.nbThread)
    
    def getValue(self, threadNumber, runNumber):
        '''
           Get a randomized msisdn
           parameter:
             params - a string with ',' delimiter
                 string[0]=>thread number (grinderThreadNumber)
                 string[1]=>run number (grinderRunNumber)
        '''
        msisdn=''
        # To manage limits
        if self.counter >= (self.max_msisdn-self.min_msisdn+1):
            return ('-1')
        
        if self.generation_mode in ('RANDOM'):
            msisdn=self.__class__.msisdn[runNumber*self.nbThread+threadNumber]
        elif self.generation_mode in ('SEQUENTIAL'):
            msisdn=self.min_msisdn+runNumber*self.nbThread+threadNumber
        else:
            # increase even msisdn starting from min
            if self.counter%2 ==0:
                msisdn=self.min_msisdn+runNumber*self.nbThread+threadNumber
            # decrease odd numbers starting from max
            else:
                msisdn=self.max_msisdn- (runNumber*self.nbThread+threadNumber)
                
        self.counter=self.counter+1

        return str(msisdn)
    
    def getPrefixedValue(self, threadNumber, runNumber):
        return ('+%s'% self.getValue(threadNumber, runNumber) )
    
    def getName(self):
        return self.__class__.__name__
    
    def getCount(self):
        return self.counter



if __name__ == '__main__':
    pass