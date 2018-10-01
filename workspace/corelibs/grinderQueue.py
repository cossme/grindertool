'''
Created on 19 sept. 2014

@author: omerlin
'''
from __future__ import with_statement

from Queue import Queue, Empty
from java.lang import Thread
from threading import Lock

from corelibs.contextLock import ContextLock
from corelibs.coreGrinder  import CoreGrinder
from corelibs.token import AbortRunToken


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

class GrinderQueue:
    '''
       A single static queue for the whole worker
       It may be feed by a throughput producer or by an asynchronous callback flow
       async parameter: if the scenario as no asynchronous step, no need to look inside the queue 
    '''
    lock=Lock()
    queue = Queue()
    throughput_mode=None
    waiting_mode = None
    pureThreadMode=False
    validationMode=False
    async=False
    graceful_period=0
    
    @classmethod
    def setFlags(cls, **kargs):
        '''
            Must be called ** ONE TIME ** from Configuration() in the initialization part
            This is to avoid circular reference import of the Configuration class
        '''
        cls.validationMode=kargs['validationMode']
        cls.async=kargs['async']
        cls.pureThreadMode=kargs['pureThreadMode']
        cls.waiting_mode=kargs['waiting_mode']
        cls.throughput_mode=kargs['throughput']
        
        if cls.async:
            cls.graceful_period=kargs['graceful_async']
        
        # 3 cases:
        #    1) pure throughput mode
        #    2) thread mode (many threads) and starting on an event (waiting_mode)
        #    3) validation mode (thread=1 or validation forced "validationMode=True" and no async mode )
        #
        if cls.throughput_mode or (cls.pureThreadMode and cls.waiting_mode) or (cls.validationMode and not cls.async):
            # monkey patching
            cls.take=cls.blocking_take

       
        
    @classmethod
    def blocking_take(cls):
        '''
           This is called by a class.take() thru monkey patching in cls.setFalgs()
        '''
        try:
            return cls.queue.get(True)
        except Exception, e:
            print 'blocking_take() exception: %s' % (str(e))
            pass
        finally:
            print 'blocking_take() - got a session'
    
    @classmethod
    def take(cls, pollInterval=10):
        '''
           This is the validation mode with some async steps
           ### WARNING ### This code is overloaded at runtime by "bloking_take()" - monkey patching !!!!!
           
        :param cls:
        :param pollInterval: a time for polling on the queue
        '''
        #
        # PLS, read the warning above !
        #
        logger.debug('take() - ValidationMode - [ContextLock=%d]' % (ContextLock.count()))

        # VIRTUALRUNS #
        # Among the virtual run, this one is for the normal scenario termination
        ContextLock.asyncCounterDecrease()

        #
        # We may get an asynchronous message,
        # Check the queue but after a small amount of sleep
        # If we come back too fastly with AbortRunToken(), we risk to consume all grinder "runs" aimed at executing asyn steps
        #
        Thread.sleep(500)
        
        try:
            return cls.queue.get(False)      
        except Empty:
            pass
        
        # VIRTUALRUNS #
        # This is the real number of runs to execute in async mode
        if ContextLock.getAsyncCounterValue()<0:
            return AbortRunToken()
        
        #
        if ContextLock.count()<=0:
            logger.debug('take() - No more ContextLock - returning')
            return None
                                
        # Wait after async callback Or waiting async timeout
        while( True) :
            logger.trace('take() - [ContextLock=%d] - Waiting after token (%s seconds) ...' % (ContextLock.count(), pollInterval))
            try:
                token=cls.queue.get(True,pollInterval)
                logger.debug('Got a token of type: %s, class: %s' % (type(token), token.__class__.__name__))
                return token
            except Empty:
                pass
            print '.'
            # ContextLock might be updated in the timeout reaper thread
            if ContextLock.count()<=0:
                try:
                    return cls.queue.get(False)      
                except Empty:
                    return None
                                        
        
    
    @staticmethod
    def put(token):
        GrinderQueue.queue.put(token)

    @staticmethod
    def getQueue():
        return GrinderQueue.queue
    
    @classmethod
    def clear(cls):
        with cls.lock:
            cls.queue.queue.clear()
    
    