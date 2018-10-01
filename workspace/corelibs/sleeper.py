'''
Created on 30 juil. 2014

@author: omerlin
'''
from Queue import Queue
from threading import Condition
import time

# Java librairies
from java.lang import Thread, Runnable

#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

# because heappush and heapop are not thread safe
cv=Condition()

# Global queue required to synchronize producer and consumer on Waiter
#===================== TimerQueue ==================
class ScenarioSleepingToken:
    def __init__(self, ident):
        '''
            Well, this is for auick implementation of TimeSleeper()
        :param id:
        '''
        self.ident = ident
    def getIdent(self):
        return self.ident  
    
    def __repr__(self):
        return 'ScenarioSleepingToken - [ident=%s]' % (self.ident)

#===========================================
# pseudo code of a TimeSleeper class
#===========================================
from heapq import heappush, heappop
class TimeSleeper():
    def __init__(self):
        
        # To store ordered by timestamp key 
        self.heapQueue = []

        # When we have to wake up a scenario, put in this queue
        self.sleeperQueue=Queue()
        
        # start the sleeper
        self.thread = Thread(TimeSleeper.__Sleeper(self), "TimeSleeper").start()
                
        
    def addNewScenarioWaiting(self, ident, sleeptime):
        '''
            Inform the TimeSleeper that a new scenario will have to be awaken later
            TODO : We should refuse the sleep time if too small (< X seconds)
            
        :param id: a unique identifier for a scenario
        :param sleeptime: the sleep time ( in seconds ) 
        '''
        cv.acquire()
        heappush( self.heapQueue, (round(time.time())+sleeptime, ident))
        cv.release()
        logger.info("TimeSleeper.addNewScenarioWaiting() - adding a scenario in TimeSleeper [ident=%s] - waking up at : %i" % ( ident , round(time.time())+sleeptime ))


    def getSleeperQueue(self):
        return self.sleeperQueue 

    class __Sleeper(Runnable):
        def __init__(self, this):
            self.this=this
            
        def run1(self):
            '''
            TODO: change hard coded values to parameters 
            TODO: This algorithm is quite complex and could be bugged 
                      - probably a critical section (Lock().acquire() is needed )
                      - and there is probably a more efficient algorithm ( a java implement ation ? )
            '''
            while True:
                if len(self.this.heapQueue)>0:
                    # The more recent event is on the top of the heap !
                    logger.info("HEAPQUEUE NOT EMPTY !!!!!!")
                    cv.acquire()
                    (targetTime, scenarioIdent) = heappop(self.this.heapQueue)
                    cv.release()
                    logger.info("I got a scenario %i %i" % ( scenarioIdent , targetTime ))
                    currlen=len(self.this.heapQueue)
                    while time.time()<targetTime:
                        # We have got some other element during the popped() interval
                        if len(self.this.heapQueue) > currlen:
                            currlen=len(self.this.heapQueue)
                            try:
                                # is it a more recent event ?
                                cv.acquire()
                                (targetTime2, scenarioIdent2) = heappop(self.this.heapQueue)
                                cv.release()
                                if targetTime2<targetTime:
                                    heappush(self.this.heapQueue, (targetTime, scenarioIdent))
                                    (targetTime, scenarioIdent) = (targetTime2, scenarioIdent2)
                                else:
                                    # Ok a check for nothing, back to the heap
                                    cv.acquire()
                                    heappush(self.this.heapQueue, (targetTime2, scenarioIdent2))
                                    cv.release()
                            except IndexError:
                                # well, the heap was already empty
                                pass
                        # Not too aggressive - second accuracy may be enough
                        time.sleep(0.1)
                    # It's time to wake up the lazzy scenario
                    # The Metronom class is consuming token pushed on the sleeperQueue
                    self.this.sleeperQueue.put(ScenarioSleepingToken(scenarioIdent))
                time.sleep(0.1)

        def run(self):
            '''
            TODO: change hard coded values to parameters 
            TODO: SIMPLER is better - it's not accurate but works for heavy load
            '''
            counter=1
            while True:
                counter+=1
                if len(self.this.heapQueue)>0:
                    # The more recent event is on the top of the heap !
                    cv.acquire()
                    (targetTime, scenarioIdent) = heappop(self.this.heapQueue)
                    cv.release()
                    if counter%10 == 0 :
                        logger.debug('[targetTime=%d][currentTime=%d][scenarioIdent=%s][heapQueueSize=%d]' % (targetTime, time.time(),
                                                                                                              scenarioIdent,len(self.this.heapQueue)))
                    counter+=1
                    while time.time()<targetTime:
                        # Not too aggressive - second accuracy may be enough
                        time.sleep(0.1)
                    # It's time to wake up the lazzy scenario
                    # The Metronom class is consuming token pushed on the sleeperQueue
                    logger.debug('__Sleeper.run() - waking up ScenarioSleepingToken %s' % (scenarioIdent))
                    self.this.sleeperQueue.put(ScenarioSleepingToken(scenarioIdent))
                if counter%10 == 0 :
                    logger.debug('Empty hash Queue - [len=%d]' % (len(self.this.heapQueue)))
                time.sleep(0.1)
            logger.warning('Defcon 1 : __Sleeper.run() - thread ends up !!!!')
