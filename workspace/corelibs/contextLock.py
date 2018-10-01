'''
Created on 30 juil. 2014

@author: omerlin
'''
from __future__ import with_statement

from threading import Condition
from corelibs.coreGrinder  import CoreGrinder

logger=CoreGrinder.getLogger()


class ContextLock:         
    # For validation Asynchronous management
    waitingContext=0
    cv_context_increase=Condition()
    cv_context_decrease=Condition()
    
    # The initial value
    asyncRunsCounter=0
    
     
    @classmethod
    def setAsyncRuns(cls, nbruns):
        cls.asyncRunsCounter = nbruns
        
    @classmethod
    def countAsyncRuns(cls):
        return cls.asyncRunsCounter
    
    @classmethod
    def asyncCounterDecrease(cls):
        if cls.asyncRunsCounter>0:
            cls.asyncRunsCounter-=1

    @classmethod
    def getAsyncCounterValue(cls):
        return cls.asyncRunsCounter
    
    
    @classmethod
    def decreaseAllCounters(cls, msg):
        '''
          Check later if waitingContext are still useful
        :param cls:
        :parma msg: the code context execution
        '''
        with cls.cv_context_decrease:
            cls.waitingContext-=1
            cls.asyncRunsCounter-=1
            logger.trace('%s [waitingContext=%s][virtualRuns=%d]' % (msg, cls.waitingContext, cls.asyncRunsCounter))

        
    #---------------------------------     
    @classmethod
    def contextDecrease(cls):
        with cls.cv_context_decrease:
            cls.waitingContext-=1

    @classmethod
    def contextIncrease(cls):
        with cls.cv_context_increase:
            cls.waitingContext+=1

    @classmethod
    def count(cls):
        return cls.waitingContext


   
        