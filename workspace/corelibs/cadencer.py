'''
Created on 30 juil. 2014

@author: omerlin
'''

from com.sun.net.httpserver import Filter, HttpHandler, HttpServer
from java.net import InetSocketAddress
import math

from corelibs.coreGrinder  import CoreGrinder
from corelibs.token import ThroughputToken, InternalBatchToken


#----------------------------------------------------------------------
# java httpserver dependencies
#----------------------------------------------------------------------
#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------
    
class Cadencer:
    '''
       abstract class
    '''
    def __init__(self):
        pass
    
class FlatCadencer(Cadencer):
    '''
        Flat means fixed regular interval of time
    '''
    def __init__(self, tps=1):
        self.tps=tps
        self._value = 1000/float(tps)
        self.has_changed=False
    
    def set(self, tps):
        self.has_changed=True
        self.tps=tps
        try:
            self._value = 1000/float(tps)
        except ZeroDivisionError:
            self._value = 10000
    
    def getTps(self):
        return self.tps
    
    def next(self):
        isChanged = self.has_changed
        self.has_changed=False
        return ThroughputToken(self._value),isChanged



    
class HttpCadencer(FlatCadencer):
    '''
        Flat means fixed TPS
    '''
    TPS=1
    def __init__(self, initStr, debug=False):
        try:
            tps,port = initStr.split(',')
        except:
            logger.error( 'Invalid - format : <tps>,<port>')
            raise
        self.set(tps)
        
        # HTTP server declaration
        self.server = HttpServer.create(InetSocketAddress(int(port)), 0);
        self.server.createContext("/cmd", self.MyHandler(self)).getFilters().add(self.ParameterParser())
        self.server.setExecutor(None)
        self.server.start()
        logger.info("HttpCadencer - Server is listening on port %d" % (port)) 
    

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
            requestMethod = exchange.getRequestMethod();
            if requestMethod == "GET":

                query = exchange.getAttribute('query')
                #str="QUERY==>"+query
                self.this.set(query.split('=')[1])
                
                
#                responseHeaders = exchange.getResponseHeaders();
#                responseHeaders.set("Content-Type", "text/plain");
#                exchange.sendResponseHeaders(200, len(str));
    
                responseBody = exchange.getResponseBody();
#                responseBody.write(str);
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



class RythmCadencer(Cadencer):
    '''
        Define a rythm ( in scenario calls per second) during a given duration in seconds
        After initialization (scenariocallspersecond, duration), you have a number(self._count) of 
        interval (self._interval)
        You have finished to consume intervals, you return -1  
    '''
    def __init__(self, rythmStr):
        '''  
        @param rythmStr: a formated string "nbTPS,duration"
        '''
        [self.tps, self.duration] = [float(k) for k in rythmStr.split(',')]
        # interval in milli seconds
        self._interval = 1000/self.tps
        # interval is longer than duration in seconds
        if self._interval/1000>self.duration:
            # ok, we take duration converted in milli seconds
            self._interval=self.duration*1000
        
        # Number of interval
        self._count=int(math.ceil(self.duration*self.tps))
        
    def getTps(self):
        return self.tps
    def getDuration(self):
        return self.duration
            
    def next(self):
        self._count -=  1
        if self._count<0:
            return ThroughputToken(-1), -1
        return ThroughputToken(self._interval), self.tps
        
    def __repr__(self):
        return "RythmCadender [count=%d][interval=%d][tps=%f][duration=%f]" % (self._count, self._interval, self.tps, self.duration)

class RampingCadencer(Cadencer):
    """
      Define a complete test rampup/rampdown with different phase
      This is defined as a string of the form
      tps1,duration1 tps2,duration2 tps3,duration3 ... tpsN,durationN
      OR
      tps1,duration1,tps2,duration2,tps3,duration3 ...,tpsN,durationN
    """
    def __init__(self, rampingStr):
        self.rampingStr = rampingStr.replace(' ',',')
        items = self.rampingStr.split(',')
        self.rc=[]
        for k in range(0,len(items),2):
            self.rc.append(RythmCadencer("%s,%s"% (items[k],items[k+1])))
        self.max=len(self.rc)
        self.inx=0
        logger.trace('RampingCadencer - INIT - [RampingCadencer=%s] [max=%d]' % (self, self.max))
        self.breaking=True
                
    def next(self):
        '''
           Get next sleep interval from RythmCadencer
           If we get -1, that means that we change interval, so we move to next RythmCadencer
           If we were at last RythmCadencer - OK - all is finished        
        '''
        if logger.isInfoEnabled():
            if self.breaking:
                logger.info( 'RampingCadencer - Break - %s' % (self.rc[self.inx]))
                self.breaking=False
                
        token,tps = self.rc[self.inx].next()
        # We have finished one interval - switch to another ?
        if token.getInterval() <0:
            self.inx += 1
            # last one
            if self.inx >= self.max:
                logger.info('RampingCadencer - Stopping -  [inx=%d],[max=%d]' % (self.inx,self.max))
                return ThroughputToken(-1), -1
            self.breaking=True
            return self.rc[self.inx].next()
        return token,tps

    def __repr__(self):
        return ','.join(['%s' % (rythmCadencer) for rythmCadencer in self.rc])

    
class Interval():
    def __init__(self,tps,duration):
        logger.debug('Interval- tps=%s, duration=%s' % (tps,duration))
        # float type
        self.tps = float(tps)
        # String here
        if duration[-1].isalpha():
            c=duration[-1]
            duration=long(duration[:-1])
            if c.lower()=='s':
                pass
            if c.lower()=='m':
                duration*=60
            elif c.lower()=='h':
                duration*=3600
            else:
                logger.error('Interval: unknown format "%s" for duration' % (c) )
                raise 'Interval: unknown format "%s" for duration' % (c)
        else:
            duration=long(duration)
        self.duration = duration
        self.nbIntervals=tps*duration
        self.interval=float(1000/tps)
        self.batchSize=1
        if self.interval<10:
            self.batchSize=10
        elif self.interval<5:
            self.batchSize=100
        elif self.interval<2:
            self.batchSize=1000
        elif self.interval<0.5:
            raise SyntaxError('Too high TPS constraint (%d)' % (self.interval))    
        self.index=0
        
    def next(self):
        self.index+=self.batchSize

        # This is the last interval        
        if self.index>self.nbIntervals:
            return None,-1
        
        token = ThroughputToken(self.interval) if self.batchSize==1 else InternalBatchToken(self.batchSize,self.interval)
        return token , self.tps
    
    def __repr__(self):
        return 'Interval [interval=%6.2fms][nb=%d][tps=%6.2f][duration=%d][batch=%d]' % (self.interval,self.nbIntervals, self.tps,self.duration, self.batchSize)

class FastCadencer(Cadencer):
    def __init__(self,rampingStr):
        self.interval=[]
        tps,duration=None,None
        for k in rampingStr.split(' '):
            try:
                x,duration=k.split(',')
                tps=float(x)
            except:
                raise SyntaxError('Interval "%s" in the ramping string "%s" is incorrect' % (k, rampingStr))
            interval=Interval(tps,duration)
            logger.debug('FastCadencer - %s - interval="%s"' % (k, interval))
            self.interval.append(interval)
        self.max=len(self.interval)
        self.current=0    
        logger.info('FastCadencer - INIT terminated - [nb Interval=%d]' % (self.max))
        self.breaking=True
    
    def next(self):
        if logger.isInfoEnabled():
            if self.breaking:
                logger.info('FastCadencer - next interval (%d) - %s' % (self.current, self.interval[self.current]))
                self.breaking=False
            
        tokens, tps = self.interval[self.current].next()
        # break - interval change
        if not tokens:
            self.breaking=True
            self.current+=1
            if self.current>=self.max:
                logger.info('FastCadencer - Stopping - no more interval')
                return ThroughputToken( -1 ), -1
            return self.interval[self.current].next()
        return tokens,tps
    
class DynamicCadencer(Cadencer):
    """
      Define a dynamic rampup. 
    """
    # this is the scan interval for file updates
    scanInterval=10
    def __init__(self, rampingStr):
        """
           rampingStr is a file containing a scenario flow rate
        """
        # TODO : make it dynamic !
        self.filename = rampingStr
        try : 
            myFile = open(rampingStr, 'r')
        except :
            print("***************** ERROR : DYNAMIC type of rampup is asked but file [%s] set by property <throughput_rampup[process_number]> that defines cadence to sustain does NOT exist" % (rampingStr))
                                                                                                                                         
        self.tps=float(myFile.readline(10))
        myFile.close()
        self._interval = 1000/self.tps
        # Number of interval ( minimum is 1 second for now ) +1 to the count to handle tps lower than 1 second.
        self._count=self.scanInterval*self.tps + 1
        print ("################ Number of scenario per seconds : %s ", self.tps )
        print ("################ Number of count for 1 second : %s ", self._count )
        
    def next(self):
        '''
           Get next sleep interval
           If we get -1, that means that we re-read the file for next interval to do
           If file reads something else than numbers, it done.
        '''
        changed=False
        self._count = self._count - 1
        if self._count<0:
            # it's NOT finished - reread file for next interval.
            myFile = open(self.filename, 'r')
            newTPS = float(myFile.readline(10))
            myFile.close()

            if newTPS != self.tps :
                print('### Requested TPS changed from %s to %s' % (self.tps, newTPS))
                self.tps = newTPS
                changed=True
                print ("################ Number of scenario per seconds : %s ", self.tps )
                print ("################ Number of count for 1 second : %s ", self._count )
                
            if self.tps==0 : 
                print("############### Got request to stop injecting ")
                return -1
            self._interval = 1000/self.tps
            # Number of interval ( minimum is 1 second for now ) +1 to the count to handle tps lower than 1 second.
            self._count=self.scanInterval*self.tps + 1

        return ThroughputToken(self._interval),changed
        
    def getTps(self):
        return self.tps
    def getDuration(self):
        return self.duration        
        
    def __repr__(self):
        return "------ Throughput given by file " + self.filename
