"""
http.grindertool 
Simple http implementation
"""
import binascii
from java.io import FileInputStream
from java.lang import Exception as JavaException, System
from java.lang import String, NoClassDefFoundError, ExceptionInInitializerError
from java.util.regex import Pattern
import os

#------------ Ignore SSL Certs
from java.security import SecureRandom
from javax.net.ssl import X509TrustManager, SSLContext
from HTTPClient import NVPair, HTTPConnection

from core import core
import corelibs
from corelibs.coreGrinder  import CoreGrinder


# Just to be able to test in standalone mode without having grinder runtime
try:
    from net.grinder.plugin.http import HTTPPluginControl, HTTPRequest
except NoClassDefFoundError,e:
    print 'Warning, import of "HTTPPluginControl, HTTPRequest" failed on package "net.grinder.plugin.http"'
    pass
except ExceptionInInitializerError,e:
    print 'Warning, import of "HTTPPluginControl, HTTPRequest" failed on package "net.grinder.plugin.http"'
    pass


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()
#----------------------------------------------------------------------

class MyTrustManager(X509TrustManager):
    '''
    set up a TrustManager that trusts everything

    Trust all certificates to avoid having to manage server certificates in the local store
    '''
    def isClientTrusted(self, chain):
        return True
    def isServerTrusted(self, chain):
        return True
    def checkServerTrusted(self, chain, string):
        pass
    def checkClientTrusted(self, chain, string):
        pass

    
class http(core):
 
    SETCOOKIE      = 'Set-Cookie'
    COOKIE         = 'Cookie'
    uriRegexp=Pattern.compile('(http[s]*)://([^:]+):(\d+)')

    # Load balance policy is one of : lineID, runID, threadID (default here), processID.
    loadBalancePolicy=(properties.get('loadBalancePolicy') or 'NONE').upper()
    
    def __init__(self,_dataFilePath, _templateFilePath):    
        core.__init__(self, _dataFilePath, _templateFilePath)       
        
        # Multipart management
        self.isMultipart=False
        # Binary management
        self.isOctetStream=False
        
        self.props=self.getProperties()        
        
        self.validateData = properties.getBoolean('http_validateData', False)
        self.validateStatus = properties.getBoolean('http_validateStatus', False)
        self.validateStatus_skipIfNotDefined = properties.getBoolean('http_validateStatus_skipIfNotDefined', False)
        self.parseHttp=properties.getBoolean('parseHTTP', False)

        self.httpErrorPattern=None
        if self.parseHttp:
            self.httpPattern=properties.get('httpPattern') or r'"snHTTPCode":([135467]\d{2})|"code":"([135467]\d{2})"' 
            self.httpErrorPattern=Pattern.compile(self.httpPattern)  
        self.httpValidPattern=None
       
        #
        # added to get the protocol of the module
        #
        self.protocol =  self.props[self.__class__.__name__+'_protocol']
        self.isDebugEnabled = logger.isDebugEnabled()
        
        #
        # SSL certificate management
        #
        self.ignoreCertificate=False
        if self.protocol=='https':
            self.ignoreCertificate=self.props.get('ignore_certificates', 'true').lower() == 'true'
            if grinder.threadNumber == 0:
                logger.info('https usage, ignore_certificates: %s. To deactivate use property "ignore_certificate=False"' % (str(self.ignoreCertificate)))
            if self.ignoreCertificate:
                self.ignoreCertificate=True
                trustAllCerts = []
                trustAllCerts.append(MyTrustManager())
                self.sslContext = SSLContext.getInstance("SSL")
                self.sslContext.init(None, trustAllCerts, SecureRandom())

        #
        # Network Proxy settings
        #
        if properties.getInt("use_proxy",0):
            connectionDefaults = HTTPPluginControl.getConnectionDefaults()
            proxy_host=properties.get("proxy_host") or 'localhost'
            proxy_port=properties.getInt("proxy_port",8001)
            connectionDefaults.setProxyServer(proxy_host, proxy_port)
            logger.info('PROXY ACTIVATED TO "%s:%s"' % (proxy_host, proxy_port),'CONSOLE')
            
        # load the loadbalance(d) hosts and ports
        try:
            self.liLBHostAndPort = loadLBHostAndPortSearchParents(self.__class__)
            if grinder.threadNumber == 0:
                logger.info('LB host,port list: "%s", [policy="%s"]' % (self.liLBHostAndPort, self.__class__.loadBalancePolicy))
        except IndexError, x:
            logger.error('>>>>> FATAL: define at least one http_host and http_port property !!')
            raise SyntaxError('FATAL: define at least one http_host and http_port property in your properties file!\n%s' %x)
        # add display for functional tests
        self.displayReadResponse = properties.getBoolean('displayReadResponse',False)
        # Mutual authentication
        if System.getProperty('javax.net.ssl.keyStore') and System.getProperty('javax.net.ssl.trustStore'):
            keyStoreFile=System.getProperty('javax.net.ssl.keyStore')
            keyStoreTrustStore=System.getProperty('javax.net.ssl.trustStore')
            if not os.path.exists(keyStoreFile):
                raise SyntaxError('[Mutual authentication] File %s do not exists' % (keyStoreFile))
            if not os.path.exists(keyStoreTrustStore):
                raise SyntaxError('[Mutual authentication] File %s do not exists' % (keyStoreTrustStore))
            if not System.getProperty('javax.net.ssl.keyStorePassword'):
                raise SyntaxError('[Mutual authentication] password "javax.net.ssl.keyStorePassword" must be defined')
            if not System.getProperty('javax.net.ssl.trustStorePassword'):
                raise SyntaxError('[Mutual authentication] password "javax.net.ssl.trustStorePassword" must be defined')
            
            grinder.SSLControl.setKeyStoreFile(keyStoreFile, System.getProperty('javax.net.ssl.keyStorePassword'),
                                               keyStoreTrustStore, System.getProperty('javax.net.ssl.trustStorePassword') )
       
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: http.grindertool 1.17 2011/09/15 14:22:45CEST omerlin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    def processResponse(self, response):      
        #
        # retrieve the necessary data (status code, errorCode, message)
        #
        liResp = {}
        liResp['httpStatCode'] = response.getStatusCode()
        # errorCode means OK for the test (no links with http status code)
        liResp['errorCode'] = 200
        liResp['responseText'] = response.text
        
        # put all the headers in the response dictionary
        for name in response.listHeaders():         
            liResp[name] = response.getHeader(name)
                                             
        return liResp       
    
    def sendData(self, **args):
        return self.sendHTTP(args['data'])

    def getResponseBody(self, responseTable):
        '''
            Separate - to allow overloading
        '''
        return responseTable['responseText']
    
    def HTTPmethod(self, method):
        methods={'GET'  : self.https_connection.Get if self.https_connection else  HTTPRequest().GET, 
                 'POST' : self.https_connection.Post if self.https_connection else  HTTPRequest().POST,
                 'PUT' : self.https_connection.Put if self.https_connection else  HTTPRequest().PUT,
                 'HEAD' : self.https_connection.Head if self.https_connection else  HTTPRequest().HEAD,
                 'DELETE' : self.https_connection.Delete if self.https_connection else  HTTPRequest().DELETE,
                 'OPTIONS' : self.https_connection.Options if self.https_connection else  HTTPRequest().OPTIONS,
                 'PATCH' : None if self.https_connection else  HTTPRequest().PATCH
                 }
        if method=='PATCH' and self.https_connection:
            raise NotImplementedError( 'Please ask for implementation to Grindertool developers !!' )
        return methods[method]
    
    def HTTPRequest(self):
        if self.https_connection:
            return self.https_connection
        return HTTPRequest()
        
            
                                              
    def callHTTP_GET(self, uri, body, http_headers):
        '''
             Separate - to allow overloading
        '''
        return self.HTTPmethod('GET')(uri, None ,http_headers)


    def callHTTP_POST_FormData(self, uri, bodyList, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        formdata=[]
        if not self.isMultipart:
            raise SyntaxError('You must have a Content-Type "multipart/form-data" !')
        else:
            logger.trace('callHTTP_POST_FormData() - body="%s"' % (bodyList))
            for line in bodyList:
                name,value=line.split()
                if name == 'FILE':
                    filename=value
                    try:
                        body=open(filename,'rb').read()
                    except:
                        raise 'Unable to read the file: %s' % (filename)
                    formdata.append(NVPair('file',body))
                    logger.debug('Appending in formdata  file %s len=%d' % (filename, len(body)))
                else:
                    formdata.append(NVPair(name,value))
                    logger.debug('Appending in formdata  [name=%s][value=%s]' % (name,value))
            
            return self.HTTPmethod('POST')(uri, formdata, http_headers, self.isMultipart)
        
        
    def callHTTP_POST_file(self, uri, filename, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        if not self.isMultipart:
            imageFileIS=FileInputStream(filename)
            return self.HTTPmethod('POST')(uri, imageFileIS, http_headers)
        else:
            formdata=[]
            body=open(filename,'rb').read()
            formdata.append(NVPair(os.path.basename(filename),body))
            if self.isDebugEnabled:
                logger.debug('Posting formdata on file %s len=%d' % (os.path.basename(filename), len(body)))
            return self.HTTPmethod('POST')(uri, formdata, http_headers, self.isMultipart)

 
    def callHTTP_PUT_file(self, uri, filename, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        imageFileIS=FileInputStream(filename)
        return self.HTTPRequest().PUT(uri, imageFileIS, http_headers)
 

    def callHTTP_PATCH_file(self, uri, filename, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        imageFileIS=FileInputStream(filename)
        return self.HTTPRequest().PATCH(uri, imageFileIS, http_headers)


    def callHTTP_DELETE(self, uri, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        return self.HTTPRequest().DELETE(uri, http_headers)

 
    def callHTTP_POST_bytes(self, uri, bytes, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        ## some cookie may cause issue, there are patches for TheGrinder for trfailing ";httpOnly" which are security patches to avoid cookie reuse
        ## see http://sourceforge.net/tracker/index.php?func=detail&aid=2952023&group_id=18598&atid=118598
        return self.HTTPmethod('POST')(uri, bytes, http_headers)
 
 
    def callHTTP_PUT_bytes(self, uri, bytes, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        return self.HTTPRequest().PUT(uri, bytes, http_headers)


    def callHTTP_PATCH_bytes(self, uri, bytes, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        return self.HTTPRequest().PATCH(uri, bytes, http_headers)


    def callHTTP_OPTIONS_bytes(self, uri, bytes, http_headers):
        '''
             Separate - to allow overloading
        '''
        ## No try / catch : know what is done using .properties, .in and .template files.
        return self.HTTPRequest().OPTIONS(uri, None, http_headers)

    def callHTTP(self, uri, body, http_headers, http_method):
        '''
             Separate - to allow overloading (see httpbinary)
        '''
        if logger.isTraceEnabled:
            logger.trace("http.callHttp : call HTTP, body is '''%s'''" % (body or '<empty>'))
        
        try:
            response=None
            if http_method == "GET":
                response = self.callHTTP_GET(uri, None ,http_headers)
            elif http_method == "OPTIONS" :
                response = self.callHTTP_OPTIONS_bytes(uri, None, http_headers);
            elif http_method == "DELETE" :
                response = self.callHTTP_DELETE(uri,  http_headers);
            else :
                if body:
                    if body.startswith("FORMDATA"):
                        logger.debug("http.callHttp sending form data as input stream using HTTP [%s]" % (http_method))
                        if   http_method != "POST":
                            raise SyntaxError('FORMDATA must be a POST method !')
                        #
                        # Temporary - format is:
                        #-------------------------------
                        #    FORMDATA;<formdata1>;<formdata2>, ...;<formdataN>
                        #    where formdata<i> is of the form: name value  (so a whitespace delimiter between name and value)
                        #          name: a field name or FILE keyword
                        #          value: the value of the field or the full path corresponding to the FILE keyword.
                        #
                        response= self.callHTTP_POST_FormData(uri, body.split(';')[1:], http_headers)

                    elif body.startswith("FILE:"):
                        filename=body.replace("FILE:","",1)
                        logger.debug("http.callHttp sending file [%s] as input stream using HTTP [%s]" % (filename,http_method))
                        if   http_method == "POST": response= self.callHTTP_POST_file(uri, filename, http_headers)
                        elif http_method == "PUT" : response= self.callHTTP_PUT_file(uri, filename, http_headers)
                        elif http_method == "PATCH" : response= self.callHTTP_PATCH_file(uri, filename, http_headers)
                        else :                      logger.error(("Unknown HTTP method : [%s]" % http_method))
                    else :
                        if self.isOctetStream:
                            bytes = binascii.a2b_hex(body)
                            logger.debug('http.callHttp  Binary octet stream converted')
                        else:
                            # body is in the template 
                            bytes = String(body).getBytes()
                        if   http_method == "POST" : response= self.callHTTP_POST_bytes(uri, bytes, http_headers)
                        elif http_method == "PUT"  : response= self.callHTTP_PUT_bytes(uri, bytes, http_headers)
                        elif http_method == "PATCH"  : response= self.callHTTP_PATCH_bytes(uri, bytes, http_headers)
                        else :                       logger.warn("Unknown HTTP method : [%s]" % http_method)
                else:
                    if   http_method == "POST": response= self.callHTTP_POST_bytes(uri, None, http_headers)
                    elif http_method == "PUT"  : response= self.callHTTP_PUT_bytes(uri, None, http_headers)
                    elif http_method == "PATCH"  : response= self.callHTTP_PATCH_bytes(uri, None, http_headers)
                    else :    logger.warn("Unknown HTTP method : [%s]" % http_method)
                    
        except JavaException,e:
            raise Exception(e)
        
        if logger.isDebugEnabled:
            logger.trace("URI: [%s] - Sent Body = '''%s'''" % (uri, body or '<empty>'))
            logger.debug("DEBUG. http.callHttp  : response got. returning it")               
        return response
    
    # Set http header to NVPair() format
    def createHttpHeaders(self, headers):
        if not headers:
            return []                    
        hash_headers = dict( (header.split(':',1)[0].strip() , header.split(':',1)[1].strip() )  for header in headers if header.find(':')>=0) 
        if 'Content-Type' in hash_headers:
            self.isMultipart =  hash_headers['Content-Type'] ==   'multipart/form-data'
            self.isOctetStream = hash_headers['Content-Type'] == 'application/octet-stream'
        return [NVPair(k,v) for k,v in hash_headers.iteritems()]

    
    def _reportError(self, response,uri,requestKey,responseKey,indexNo,statusCode,statusCodeExpected):
        response['breakdown'] = 'True'
        response['errorCode'] = -1
        grinder.getStatistics().getForCurrentTest().success=0
        if 'errorMessage' in response:
            logger.error(response['errorMessage'])
        if self.isDebugEnabled:
            logger.debug(" uri is [%s]" % (uri))
            logger.debug("requestKey [%s]" % (requestKey))
            logger.debug(" responseKey [%s]" % (responseKey))
            logger.debug("indexNo [%s]" % (indexNo))
            logger.debug(" statusCode [%s]" % (statusCode))
            logger.debug("statusCodeExpected [%s]" % (statusCodeExpected))
        return response
  
    def _printOutRequest(self, args):  
        lenBody=len(args['body'])
        s ='\n'+'-'*50
        s+='\n*** Http-Out request:'
        s+='\n>> %-15s: %s' % ('test',args['testname'])
        s+='\n>> %-15s: %s' % ('Uri' ,args['uri'])
        s+='\n>> %-15s: %s' % ('method',args['method'])
        s+='\n>> %-15s:' % ('Headers')
        for k, v in args['headers'].iteritems():
            s+='\n>>\t\t\t%-25s: %s' % (k,v)
        s+='\n>> %-15s: %s' % ('Body len',str(lenBody))
        if lenBody<1025:
            s+='\n>> %-15s: %s' % ('Body',str(args['body']))
        s+='\n'+'-'*50
        logger.debug('%s' % (s))

    def _printInRequest(self, args, response):  
        body = self.getResponseBody(args)
        s ='\n'+'-'*50
        s+='\n*** Http-In request:'
        s+='\n<< %-15s: %s' % ('Status code',args['httpStatCode'])

        s+='\n<< %-15s:' % 'Headers'
        for name in response.listHeaders():         
            s+='\n<<\t\t\t%-25s: %s' % (name, response.getHeader(name))
        
        s+='\n<< %-15s: %s' % ('Body len',str(len(body)))
        if len(body)<1025:
            s+='\n<< %-15s: %s' % ('body',str(body))
                            
        s+='\n'+'-'*50
        logger.debug('%s' % (s))
 
    def callSimpleHTTP(self, uri, body, http_headers, http_method):
        '''
             Separate - to allow overloading (see httpbinary)
        '''
        if http_method == "GET":
            return self.HTTPmethod('GET')(uri, None, http_headers)
        elif http_method == "POST":
            logger.debug('callSimpleHTTP - POST - http_headers: %s' % http_headers)
            return self.HTTPmethod('POST')(uri, body, http_headers)
        elif http_method == "POST":
            return self.HTTPRequest().PUT(uri, body, http_headers)
        elif http_method == "PATCH":
            return self.HTTPRequest().PATCH(uri, body, http_headers)
        elif http_method == "OPTIONS":
            return self.HTTPRequest().OPTIONS(uri, None, http_headers)
        elif http_method == "DELETE":
            return self.HTTPRequest().DELETE(uri, http_headers)
        else:
            logger.error('Unsupported method: %s' % (http_method))
            raise NotImplemented('Unsupported on Not implemented method: %s' % (http_method))

    def sendSimpleHTTP(self, **args):
        '''
          Http protocol call without templating
          Written reduce internal processing overhead to a minimum
        '''
        if logger.isDebugEnabled():
            self._printOutRequest(args)
        
        # Manage ignoring certificates
        self.__manageSSL_for_uri(args['uri'])
        
        # LB implementation (to be reviewed)
        # LBhost, LBport = self.getLBHostAndPortWithID()
        liResp = {}
        
        # Set http header to NVPair() format
        self.isMultipart = args['headers']['Content-Type'] == 'multipart/form-data'
        self.isOctetStream = args['headers']['Content-Type'] == 'application/octet-stream'
        http_headers = [NVPair(k, v) for k, v in args['headers'].iteritems()]
        logger.debug('sendSimpleHTTP - http_headers: %s' % http_headers)

        # check reporter
        if 'reporter' in args and args['reporter']:
            # Low overhead call (minimum processing)
            startTime = System.currentTimeMillis()
            try:
                response = self.callSimpleHTTP(args['uri'], args['body'], http_headers, args['method'])
            finally:
                deltaTime= System.currentTimeMillis() - startTime
                args['reporter'].setTime2(deltaTime, args['testname'])
                if logger.isTraceEnabled():
                    logger.trace('Test "%s" execution time : %d' % (args['testname'], deltaTime))
                liResp['grindertool.step.executionTime']=deltaTime                          
        else:
            response = self.callSimpleHTTP(args['uri'], args['body'], http_headers, args['method'])

        liResp = self.processResponse(response)

        if logger.isDebugEnabled():
            self._printInRequest(liResp, response)
       
        return liResp

    def __manageSSL_for_uri(self, uri):
        # get host & port from uri
        m=self.uriRegexp.matcher(uri)
        if not m.find():
            raise SyntaxError('Invalid URI format : "%s"' % uri)
        self.__manageSSL(m.group(1), m.group(2), m.group(3))

    def __manageSSL(self, protocol, host, port):
        self.https_connection = None
        if self.ignoreCertificate:
            self.https_connection = HTTPConnection('https', host, int(port))
            self.https_connection.setSSLSocketFactory(self.sslContext.getSocketFactory())
            self.https_connection.setRawMode(True)
            self.https_connection.setCheckCertificates(False)

    def sendHTTP(self, str2send):
        """ build the http request, send it and receive the response
        return the response"""
          
        # Base LoadBalance on some ID.
        LBhost, LBport = self.getLBHostAndPortWithID()
        logger.debug('Should connect to "%s:%s"' % (LBhost, LBport))
        
        config = self.setProperties(str2send)
        body = ""
        uri = ""
        indexNo = 0
        headers=None
              
        liResp = {}
        ################ Should be a self.cookie !!!!!!!!!! #########################
        cookie = ''
        
        while True:      
            requestKey  = "request%d"  % indexNo
            responseKey = "response%d" % indexNo
            
            if not config.has_key(requestKey+".uri"):
                logger.debug("http.py - [index=%d] - NO more URI in the scenario => End Transaction" % (indexNo))
                # TODO : write a better http implementation - getting rid of old format ( pure Yaml )
                if indexNo == 0:
                    logger.error('You must define the mandatory key "uri" in your http protocol template')
                break
            
            # reuse previous Uri if not defined at this step
            uri     = config.get(requestKey+".uri", uri)
            body    = config.get(requestKey+".body", "") or None
            http_method  = config.get(requestKey+".method", 'POST' if body else 'GET' )                    

            #
            # Host,port change management
            #
            if uri[0] == '/':
                uri = '%s://%s:%s%s' % (self.protocol,LBhost,LBport,uri)    
            logger.debug( 'calling method %s on uri: %s' % (http_method,uri))            
             
            # Manage ignoring certificates
            self.__manageSSL(self.protocol,LBhost,LBport)   
                   
            #----------------
            #  COOKIES
            #-----------------            
            #
            storedCookies= [ v for k,v in liResp.iteritems() if k.find('cookie')>=0]
            if http.SETCOOKIE in liResp or storedCookies:
                if  http.SETCOOKIE in liResp:
                    storedCookies =  storedCookies.append(liResp[http.SETCOOKIE]) 
                logger.debug("Cookie = [%s]" % storedCookies)            
            if storedCookies:    
                logger.debug("Appending cookie = [%s]" % cookie)
                headers.append(http.COOKIE + ": " + ';'.join( storedCookies ) )
            
            #----------------
            #  HEADERS
            #-----------------            
            # To manage case where header contains | as separator
            #
            http_headers=[]
            header_separator=config.get(requestKey+".header_separator") or '|'
            if config.has_key(requestKey+".headers"):
                headers = config.get(requestKey+".headers", "").split(header_separator[0])        
                # Set http header to NVPair() format
                http_headers=self.createHttpHeaders(headers)
            else:
                logger.warn("You have no headers in your scenario (requestx.headers key)")               
            
            if self.displayReadResponse:
                print('%s uri <\'%s\'>' % ("<" *4,uri))
                for header in headers:
                    print( '\t%s' % header)
                print('%s body < %s >' % ("<" *4,body))
                
                
            response = self.callHTTP(uri, body, http_headers, http_method)
            
            
            liResp = self.processResponse(response)
            
            statusCode = liResp['httpStatCode']
            responseBody = self.getResponseBody(liResp)
            
            if self.isDebugEnabled:
                logger.debug("response body : '''%s'''" % responseBody)
                logger.debug("Status Code = [%d]" % statusCode)
                        
            delay = config.get(responseKey+".delay_ms") or None
            if delay and delay != '0':
                logger.debug('... Think time: %s' % (delay))
                grinder.sleep(int(delay)) 
            
            
            if self.validateStatus:      
                if self.validateStatus_skipIfNotDefined and not config.get(responseKey+'.statuscode'):
                    statusCodeExpected=None
                else:
                    statusCodeExpected = int(config.get(responseKey+'.statuscode') or 200)
                if self.isDebugEnabled: 
                    logger.debug('StatusCode Expected: [%d]' % statusCodeExpected if statusCodeExpected else 'UnDefined') 
                if statusCodeExpected and statusCodeExpected != statusCode:
                    logger.error('expected [%d]' % statusCodeExpected)
                    logger.error('received [%d]' % statusCode)       
                    liResp['errorMessage']= "RunID %s Unexpected Status '%s' received. (expected %s)" % (self.runID,statusCode,statusCodeExpected)
                    self._reportError(liResp,uri,requestKey,responseKey,indexNo,statusCode,statusCodeExpected)                                 
                    break
                    
            if self.validateData:
                dataExpected = config.get(responseKey+".body", "")
                if self.isDebugEnabled : 
                    logger.debug("uri is [%s]" % uri)       
                    logger.debug("http.sendHTTP [self.validateData] : looking for [%s.body] in config" % responseKey)
                    logger.trace("http.sendHTTP Body Expected: [%s]" % dataExpected)

                if dataExpected == "NONE" :  
                    # Check that we did not receive anything.
                    if responseBody and responseBody != ""  :
                        logger.error("no body expected in response, got one [%s]" %  responseBody)
                        grinder.getStatistics().getForCurrentTest().success=0
                        break
                    else :
                        logger.debug("### OK, no response got")
                        break
                else :
                    match = Pattern.compile(dataExpected).matcher(responseBody)
                    # This missbehave (outOfMemory) on very large chunk of data ( e.g. 38MB ) 
                    if dataExpected and not match.find():
                        liResp['errorMessage']="Body received error \n expected [%s]\n received [%s]" % (dataExpected,responseBody)
                        logger.error("expected [%s]" % (dataExpected))
                        logger.error("received [%s]" % (responseBody))
                        self._reportError(liResp,uri,requestKey,responseKey,indexNo,statusCode,statusCodeExpected)
                        break
            
            if self.parseHttp: 
                patternExpected = config.get(responseKey+".errorPattern", "")
                if patternExpected:
                    # some Java Out of Memory error on calling logger.info, changed for "if debug"
                    logger.debug("Error Pattern Expected: [%s]" % (patternExpected))
                    self.httpErrorPattern=Pattern.compile(patternExpected)
                    
                if self.isDebugEnabled:
                    logger.trace('Looking for pattern "%s" in body \'\'\'%s\'\'\'' % (self.httpErrorPattern, responseBody))
                m = self.httpErrorPattern.matcher(responseBody)
                if m.find():
                    if len(m.groupCount())>0:
                        logger.error( '**** GOT Error codes : "%s"' % str(m.group(1)))
                        logger.error('Functional error detected with code : "%s"' % (str(m.group(1))))
                        self._reportError(liResp,uri,requestKey,responseKey,indexNo,statusCode,statusCodeExpected)
                    break

                patternExpected = config.get(responseKey+".validationPattern", "")
                if patternExpected:
                    logger.debug("Pattern Expected: [%s]" % patternExpected)
                    self.httpValidPattern=Pattern.compile(patternExpected)
                    if self.isDebugEnabled:
                        logger.trace('Looking for pattern "%s" in body "%s"' % (self.httpPattern, responseBody))
                    m = self.httpValidPattern.matcher(responseBody)
                    if not m.find():
                        liResp['errorMessage']="Error: Valid pattern '%s' Not found in body '''%s'''" % (self.httpPattern, responseBody)
                        self._reportError(liResp,uri,requestKey,responseKey,indexNo,statusCode,statusCodeExpected)
                        break
            indexNo = indexNo + 1
    
    
        return liResp



    def getProperties(self):
        """get the host/port/uri & get/post method from the grindertool file
        and insert them into a list
        return the list"""
    
        # load values
        di = {}     
        di['http_protocol'] = properties.get('http_protocol') or 'http'
        
        ### TODO: change this awful code !
        url_per_process=False
        if properties.get('grindertool.processes')>0:
            urls=(properties.get('http_url') or '').split(',') or None
            if urls:
                no=grinder.processNumber
                if logger.isDebugEnabled():
                    if grinder.threadNumber == 0:
                        logger.debug('urls='+str(urls))
                        logger.debug('processNumber=%d' % (no))
                try:
                    logger.debug('url=%s, processNumber=%d' %(urls[no],no))
                    di['http_host']=urls[no].split(':')[0]
                    di['http_port']=urls[no].split(':')[1]
                    url_per_process=True
                except:
                    logger.warn('Invalid format for http_url, should be: host1:port1,host2:port2 (...), got "%s"' % (properties.get('http_url')))
        
        if not url_per_process:
            di['http_host'] = properties.get('http_host')
            di['http_port'] = properties.get('http_port') 
            di[self.__class__.__name__+'_protocol'] = properties.get(self.__class__.__name__+'_protocol') or di['http_protocol']
        
        if logger.isDebugEnabled():
            if grinder.threadNumber == 0:   
                logger.debug('properties "%s"' % di)
        return di

    
    def getLBHostAndPortWithID(self):
        # get the load balanced host and port to send the transaction to
        # here TODO : allow different ways to do the LB ( threadID, rundID, processID, date in milli, random ... )
        policyApplied = {'NONE' : None,
                 'THREADID' : grinder.threadNumber, 'PROCESSID': CoreGrinder.getRealProcessNumber(), 
                 'RUNID' : grinder.runNumber, 'AGENTID': grinder.agentNumber, 'LINEID': self.lineID }[self.__class__.loadBalancePolicy]
        
        LBhost, LBport = corelibs.toolbox.getLBHostAndPortWithID(self.liLBHostAndPort, policyApplied)
                
        if self.isDebugEnabled:
            logger.debug ('getLBHostAndPortWithID() - [policy=%s][policy value=%s] - Connection to "%s:%s"' % (self.__class__.loadBalancePolicy, policyApplied, LBhost, LBport))    
        
        return LBhost, LBport
    
def loadLBHostAndPortSearchParents(cls):
    '''
    retreive hosts and ports  by introspection on real implementation at runtime
    this is done at init time ( else it would be ressource consuming )
    Will fail if nothing is defined, no more warnings thna just the error : 
     .properties file needs to have implementation defined.

    :param cls:
    '''
    hostPortTable = corelibs.toolbox.loadLBHostAndPort(cls.__name__)
    if hostPortTable[0] and hostPortTable[1]:
        if grinder.threadNumber == 0:
            logger.debug('loadLBHostAndPortSearchParents(%s) - Found host(s) and port(s) for implementation' % (cls.__name__))
        return hostPortTable
    
    # If nothing is set, apply parent ( standard and backward compatible ) method )
    logger.error("No host(s) and port(s) defined for implementation [%s]. Go find in parent [%s]" % (cls.__name__, cls.__bases__[0].__name__))
    # Get the first parent name by introspection and climb until getting implementation with a good setting.
    ## Method works only if not working with multi-inheritance.
    ## Method 1 : need  to import inspect
    ## Method1 : self.liLBHostAndPort = toolbox.loadLBHostAndPort((inspect.getclasstree([self.__class__])[0][0].__name__))
    ## Method2 : direct call.
    return loadLBHostAndPortSearchParents(cls.__bases__[0])


