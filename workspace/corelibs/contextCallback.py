'''
Created on 12 oct. 2014

@author: omerlin
'''
from com.sun.net.httpserver import HttpServer, HttpHandler
from java.io import BufferedReader, InputStreamReader, IOException
from java.net import InetSocketAddress
from java.util.concurrent import Executors

from net.sf.json import JSONSerializer, JSONException

from corelibs.asynclog import asynclog
from corelibs.contextIdentifier import ContextIdentifier
from corelibs.coreGrinder  import CoreGrinder
from corelibs.grinderQueue import GrinderQueue
from corelibs.token import AsyncContextToken, Token


logger=CoreGrinder.getLogger()
properties=CoreGrinder.getProperty()

    
class CallbackHandler(HttpHandler):
    
    
    def __init__(self):
        pass
     
    def __checkAttribute(self, json_data, attribute):
        try:
            return json_data.get(attribute)
        except:
            logger.error('[contextCallback] required attribute "%s" was not found in JSON "%s"' % (attribute, json_data))
            raise SyntaxError('[contextCallback] required attribute "%s" was not found in JSON "%s"' % (attribute, json_data))
    
    def __manage(self, data):
        
        # This is a async token - with a Json format
        try:
            logger.debug('[%s] Transforming a "%s" data to a Json AsyncContextToken()' %  (self.__class__.__name__,data))
            json_data= JSONSerializer.toJSON(data)                       
        except JSONException, x:
            raise SyntaxError("%s\nfailed to read json: '''%s'''" % (x, data))

        # checking required attributes
        contextKey=self.__checkAttribute(json_data, 'contextKey')
        contextValue=self.__checkAttribute(json_data, 'value')
        
        # Checking data attribute
        try:
            data_dict=dict(json_data.get('data'))
            asynclog.log(pos='%s.__manage' %(self.__class__.__name__), key=contextKey,value=contextValue, 
                         msg='Got data: %s' % (data_dict))    
        except:
            logger.error('[%s] the "data" attribute must be a dictionary' %(self.__class__.__name__))
            raise SyntaxError('[%s] the "data" attribute must be a dictionary'%(self.__class__.__name__))        
                            
        __ctx=ContextIdentifier.exists(contextKey,contextValue)
        if __ctx:        
            try:
                # The context has not been released
                # we update the context with notification data
                # and flag the context that a callback event occurred                
                if ContextIdentifier.lock_and_update_flag(__ctx, data_dict):
                    return 
                
                # The processing for the current context is terminated
                # Creating the AsyncContextToken
                asynclog.log(pos='%s.__manage' %(self.__class__.__name__), key=contextKey,value=contextValue, msg='LOCK IS DOWN', ctx=__ctx)    
                token=AsyncContextToken(contextKey, contextValue, data_dict)
                
                # Adding the token to the main processing queue
                GrinderQueue.put( token  )
                
                return
            except Exception, e:
                logger.error('<<ASYNC>>[%s=%s][%s.__manage] context management ,reason: %s' % (contextKey,contextValue,self.__class__.__name__,e))
                raise(e)            
        # 
        # Anomaly : If we are here, it means, the context is no more in the cache
        #           Either it's real problem either the context has expired 
        #
        try:
            asynclog.logError(pos='%s.__manage' %(self.__class__.__name__), key=contextKey,value=contextValue,
                              msg='IGNORED Unknown EVENT (Expiration occurred or real processing error)', err='Unknown EVENT received' )
            if logger.isTraceEnabled():
                logger.trace(ContextIdentifier.printall())
        except Exception, e:
            logger.error('<<ASYNC>>[%s=%s][%s.__manage] No ctx found () !, reason: %s' % (contextKey,contextValue,self.__class__.__name__,e))
            raise(e)
            
    def handle(self, httpExchange):
        try:
            method = httpExchange.getRequestMethod()
            requestHeaders = httpExchange.getRequestHeaders()
            contentType=requestHeaders.getFirst('Content-Type')
            if method=='POST' and contentType=='application/json':
                try:
                    br = BufferedReader( InputStreamReader (httpExchange.getRequestBody()))
                    if br :
                        data=br.readLine()
                        br.close()
                        self.__manage(data)
                    else:
                        logger.error('[contextCallback.handle] %s : No data in the Json request' % (self.__class__.__name__))
                except Exception, e:
                    logger.error('(handle) Exception- %s : stacktrace=%s' % (self.__class__.__name__, e))                
                    
                logger.trace('[contextCallback.handle] Answering 200 to the request')
                httpExchange.sendResponseHeaders(200, -1L)
            else:
                httpExchange.sendResponseHeaders(404, -1L)
                logger.warn('[method=%s][Content-Type=%s] are incorrect, waiting for [method=POST][Content-Type=application/json]' % (method, contentType))
            
        except IOException, e:
            logger.error('IOException- %s : stacktrace=%s' % (self.__class__.__name__, e))            
        finally:
            httpExchange.close()

class StartHandler(HttpHandler):
    
# Doc: http://docs.oracle.com/javase/8/docs/jre/api/net/httpserver/spec/com/sun/net/httpserver/HttpExchange.html
    
    def handle(self, httpExchange):
        try:
            method = httpExchange.getRequestMethod()

            # Something like:
            #   /start?scenario=first
            print httpExchange.getRequestURI()

            if method=='GET':
                ########## We should better add a Context Token with an init having the request updated by param content !!!
                GrinderQueue.put( Token(10)  )   
                logger.trace('[Start handler] Answering 200 to the request')
                httpExchange.sendResponseHeaders(200, -1L)
            else:
                httpExchange.sendResponseHeaders(404, -1L)
                logger.warn('[method=%s] is incorrect, waiting for [method=GET]' % (method))
            
        except IOException, e:
            logger.error('(handle) IOException- %s : stacktrace=%s' % (self.__class__.__name__, e))            
        finally:
            httpExchange.close()


class HTTPServerCallback:
    
    contextIdentifier=None
    host = None
    port = None
    poolsize = 0
    socketBackLog = None
    httpServer=None

 
    @classmethod
    def initialize(cls, host, port, poolsize, socketBackLog, contextIdentifier=None):
        cls.host = host
        cls.port = port
        cls.poolsize = poolsize
        cls.socketBackLog = socketBackLog
        cls.httpServer=None
        cls.contextIdentifier=contextIdentifier
        
    @classmethod 
    def start(cls):
        try:
            inetSocketAddress = InetSocketAddress(cls.host, cls.port)
            cls.httpServer = HttpServer.create(inetSocketAddress, cls.socketBackLog)
            cls.httpServer.createContext("/callback", CallbackHandler())
            cls.httpServer.createContext("/start", StartHandler())
            cls.httpServer.setExecutor(Executors.newFixedThreadPool(cls.poolsize))
            cls.httpServer.start()
            logger.info( "HTTPServerCallback is listening on %s %s" % (cls.host, cls.port))
        except IOException, e:
            logger.error('(start) %s : stacktrace=%s' % (cls.__name__, e))
            raise UnboundLocalError('(start) %s : stacktrace=%s' % (cls.__name__, e))
     
    @classmethod 
    def stop(cls):
        if cls.httpServer:
            # without waiting
            cls.httpServer.stop(0)
            logger.debug('[%s.stop] http server stopped' % (cls.__name__))

    @classmethod 
    def getHost(cls):
        return cls.host
    
    @classmethod 
    def getPort(cls):
        return cls.port
             

if __name__ == '__main__':
    HTTPServerCallback.initialize('localhost', 8080, 16, 256)
    HTTPServerCallback.start()
    
