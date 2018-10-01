'''
@summary: 
    An implementation of producer/consumers design pattern  with Java blockingQueue
    This implementation has been done to add the throughput management to TheGrinder
    ------------------------------------------------------------------------------------
  
@note:   How to include in TheGrinder code ?

from tamtam import Metronom
...
# tamtam rampup defines the number of call is made on the Grinder process per second.
# One scenario call may implies as many transaction as there are lines in the scenario.
# Thus, TPS is the ( rampup value * number of lines for the scenario ).
# 1 scenario call during 5 seconds, then 5 scenario call / 10seconds ...
# you can put also 0.2/300 (1 scenario call every 5 seconds during 300 seconds)
metronom = Metronom( 'RAMPING', "1,5 5,10 30,10 5,10")
...
class TestRunner:
    def __init__(self):
        ...
    
    def __call__(self):
        #
        # Should be the first 
        # all threads wait for the token from the Metronom producer
        # 
        if metronom.getToken() == -1:
            print "Thread %d - Arghhh! - after %d runs" % (grindertool.threadNumber, grindertool.runNumber)
            grindertool.stopThisWorkerThread()

    
    TODO : manage the threads starvation (not enough threads to consume producer tokens)
    TODO : allow changing throughput dynamically (by scanning property file and then changing Metronom policy)

@author: omerlin, 2010
'''
from java.lang import Thread, Runnable

from corelibs.cadencer import FlatCadencer, DynamicCadencer, RampingCadencer, RythmCadencer, \
    FastCadencer
from corelibs.coreGrinder  import CoreGrinder
from corelibs.grinderQueue import GrinderQueue
from corelibs.token import Token, InternalBatchToken, ThroughputToken


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------



class __Metronom:
    def __init__(self, func, nbConsumers, targetRuns, reporter=None):
        self.thread=Thread(__Metronom.__Producer( func, nbConsumers, targetRuns, reporter), "TheMetronomProducer")
        logger.info("Metronom - INIT - started for func=%s with %d consumers..." % (func.__class__.__name__,nbConsumers))      
        

    def start(self):
        self.thread.start()
        
    class __Producer(Runnable):
        '''
          A runnable inner class that just product tempo (Oject()) every Cadencer tempo 
        '''
        def __init__(self, func,nbConsumers,targetRuns, reporter=None, ):
            self._queue = GrinderQueue.getQueue()
            self.targetRuns=999999999 if targetRuns==-1 else targetRuns
            self.foo = func
            self.nbConsumers=nbConsumers 
            self.reporter=reporter
            self._inc=0
            logger.info('Producer - INIT - [class=%s][id=%s]' % (self.foo.__class__.__name__, id(self.foo)))

        def __stopAll(self):
            logger.info( "Producer stop BEGIN")
            
            # TODO
            #-------
            # MANAGE A CLEVER GRACEFUL PERIOD BASED ON GrinderQueue() waiting content
            #
            
            # Graceful period for Async
            if GrinderQueue.async:
                logger.debug('[%s.__stopAll] Async graceful period [%d millisec]' % (self.__class__.__name__, GrinderQueue.graceful_period))
                print 'Async graceful period [%d millisec] started ...' % (GrinderQueue.graceful_period)
                Thread.sleep(GrinderQueue.graceful_period)
            
            # Clean up any tokens still in the queue
            size=len(self._queue.queue)
            if size>0: 
                logger.error('(stopAll) Producer - Potential issue in your test (Thread starvation) - removing approximatively "%d" tokens' % (size))
                
            # Cleaning up anyway
            self._queue.queue.clear()
            
            # The trick is to poison all consumer to force them to stop
            for _ in range(self.nbConsumers):
                self._queue.put(Token(-1))
                Thread.sleep(5)
            
            logger.info( "Producer stop END")
                           
        def __producer__(self):
            
            logger.info( 'Producer start - [target=%d]' % (self.targetRuns))
            old_tps=0
            if self.reporter:
                self.reporter.setTPS( 0 )            
            
            # To set first TPS
            try:
                (token, tps) = self.foo.next()
            except Exception , e:
                print 'self.foo: %s failed, reason: %s' % (self.foo.__class__.__name__, e)
                logger.error('self.foo: %s failed, reason: %s' % (type(self.foo), e))
                raise
            
            self._inc+=token.getIncrement()
            logger.info('Producer first run - [TPS=%s][target=%d]' % (tps,self.targetRuns))
            if self.reporter:
                self.reporter.setTPS( tps )            
            
            while (self._inc <= self.targetRuns) :

                (token,tps) = self.foo.next()
                interval=long(token.getInterval())
                    
                if logger.isTraceEnabled():
                    logger.trace('Producer - [token=%s]' % (str(token)))
                
                # Condition to stop : -1
                if interval<0:
                    logger.info('Producer stop asked - TPS=%s' % (tps))
                    break
                
                # Changing rate
                if tps != old_tps:
                    old_tps=tps
                    
                    logger.info( 'Producer Break - [TPS=%s]%s' % (tps, token))
                    
                    # Reset queue
                    self._queue.queue.clear()
                    
                    # Tell reporter we have a new TPS
                    if self.reporter:
                        self.reporter.setTPS( tps )
                
                
                # store the token to the grinder queue
                self._inc += token.getIncrement()
                
                # to be accurate we share sleep with all consumers thread
                if isinstance(token, InternalBatchToken):
                    [self._queue.put(ThroughputToken(k, True)) for k in token.data]
                else:
                    self._queue.put(token)
                    

                # sleep between 2 tokens or batch of token
                Thread.sleep(interval)

            
        def run(self):
            self.__producer__()
            logger.debug('[%s.run] EOF producing scenario tokens ...' % (self.__class__.__name__))
            self.__stopAll()


class Metronom:
    rampupFoo={'FLAT':FlatCadencer,
               'RYTHM':RythmCadencer,
               'RAMPING': RampingCadencer,
               'FASTRAMPING': FastCadencer,
               'DYNAMIC':DynamicCadencer}    

    def __init__(self, **kargs):
        '''
           Create the metronom 
           
        @param rampupType: FLAT, RYTHM, RAMPING 
        @param rampupProfile: a value for rampup
        @param nbConsumers: in grindertool - gringer.threadNumber
        '''
        
        # The reporting client if any
        clientReporter=kargs.get('reporter',None)
        logger.debug( 'Metronom.__init__() - reporter=%s' % (clientReporter or '<<Not defined>>') )
        
        # Check this is a supported method
        rampupType=kargs.get('method')                 
        if rampupType not in self.__class__.rampupFoo.keys():
            logger.error('Invalid keys for the metronom, should be in the list: "%s"' % (self.__class__.rampupFoo.keys()))
            raise SyntaxError('Invalid keys for the metronom, should be in the list: "%s"' % (self.__class__.rampupFoo.keys()))
        
        # Check the rampup definition
        rampupProfile=kargs.get('profile')
        
        # NbThreads
        nbConsumers=kargs.get('nbThreads')
        
        # Nb of targeted execution
        targetRuns=kargs.get('target',-1)
        
        # intializing the producer 
        function=None                 
        if isinstance(rampupType,str) or isinstance(rampupType,unicode):
            logger.debug( 'Metronom.__init__() - Rampup string=%s' % (rampupProfile) )
            try:
                function = self.__class__.rampupFoo[rampupType](rampupProfile)
            except Exception, e:
                logger.error('Error %s when Initializing the rampup function of type "%s with profile "%s" '% (e, rampupType, rampupProfile))
                raise
        
        logger.debug('Metronom - creating a Metronom thread instance. [targetRuns=%d][nbThreads=%d]' % (targetRuns,nbConsumers )) 
        self.metronom = __Metronom(function, nbConsumers, targetRuns, clientReporter)

    def start(self):
        self.metronom.start()

    def getToken(self):
        return self.queue.take()
    
    def getQueue(self):
        return self.queue


