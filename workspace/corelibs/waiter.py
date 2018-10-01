'''
Created on 30 juil. 2014

@author: omerlin
'''

from Queue import Queue

# corelibs dependencies
from corelibs.token import HttpToken

# httpserver dependencies
from com.sun.net.httpserver import Filter, HttpHandler, HttpServer
from java.net import InetSocketAddress

#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


class SetQueue(Queue):
    '''
    A python queue with a Set() implementation for the content - duplicate are banned
    '''

    def _init(self, maxsize):
        Queue._init(self, maxsize) 
        self.all_items = set()
        logger.debug('__INIT__ SetQueue()') 

    def _put(self, item):
        if item not in self.all_items:
            Queue._put(self, item) 
            self.all_items.add(item)
            logger.info('SetQueue()._put() - [item=%s][#items=%d]' % (item,len(self.all_items)) )
        else:
            logger.info('%s already in the queue !')

    def _get(self):
        item=Queue._get(self)
        return item
    
    def removeFromSet(self, token):
        self.all_items.remove(token)


class Waiter:
    '''
       abstract class
    '''
    def __init__(self):
        pass


#
# SHOULD BE SIMPLIFIED !!!
# MOVED OUTSIDE
# ------------ see toolbox.py --------------
# url = 'http://example.com/?foo=bar&one=1'
# >>> from urlparse import urlparse
# >>> urlparse(url).query
# 'foo=bar&one=1'
# >>> cgi.parse_qs(urlparse(url).query)
# {'foo': ['bar'], 'one': ['1']}
#
# 
class SlaveHttp(Waiter):
    '''
        Slave HTTP Waiter - based on external Httl client request
    '''
    TPS=1
    def __init__(self, port, debug=False):
        
        # HTTP server declaration
        self.server = HttpServer.create(InetSocketAddress(int(port)), 0);
        self.server.createContext("/cmd", self.MyHandler(self)).getFilters().add(self.ParameterParser())
        self.server.setExecutor(None)
        self.server.start()
        logger.info( "SlaveHttp - Server is listening on port %d" % (int(port))) 
        self.token = HttpToken(10)
        self.sleeperQueue=SetQueue()

    def getWaiterQueue(self):
        return self.sleeperQueue 
    
    def stop(self):
        self.server.stop(1)

    class MyHandler(HttpHandler):
        def __init__(self, this):
            '''
               Transmit the outer class to the inner class
            @param httpServer: the Outer class
            '''
            #self.instance = httpServer
            self.this=this
        
        def handle(self, exchange):
            #global sleeperQueue
            requestMethod = exchange.getRequestMethod();
            if requestMethod == "GET":

                query = exchange.getAttribute('query')
                self.this.token.setValue(query)
#                 self.this.token.setValue(query.split('=')[1])
                logger.info( 'Adding message in the sleeperQueue: %s' % (self.this.token)) 
                
                self.this.sleeperQueue.put(self.this.token)
                
                logger.debug( '>>> Writing answer')
                
                answer=str(self.this.token)
                responseHeaders = exchange.getResponseHeaders();
                responseHeaders.set("Content-Type", "text/plain");
                exchange.sendResponseHeaders(200, len(answer));
    
                responseBody = exchange.getResponseBody();
                responseBody.write(answer);
                responseBody.close();

    class ParameterParser(Filter):
        def doFilter(self, exchange, chain):
            self.parseGetParameters(exchange);
            #parsePostParameters(exchange);
            chain.doFilter(exchange)
    
        def parseGetParameters(self, exchange): #throws UnsupportedEncodingException {
            requestedUri = exchange.getRequestURI();
            query = requestedUri.getRawQuery()
            exchange.setAttribute("query",query);
