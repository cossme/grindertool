'''
Created on Sep 9, 2010

@author: omerlin
@author: wgoesgen
'''
from __future__ import with_statement
from threading import Lock
from java.lang import System

from corelibs.statsd import Connection, Client, Counter, Gauge, Timer
from corelibs.stats import ReporterBase


# from corelibs.coreGrinder  import CoreGrinder
# logger=CoreGrinder.getLogger()

class StatsdClient(ReporterBase):
    sessionCount=0
    sessionLock=Lock()

    def __init__(self, host, port, location):
        self.scenario_name=location or 'grinder'
        self.host=host
        self.port=port
        self.client=Client(name=self.scenario_name,
                           connection=Connection(host=self.host, port=self.port, sample_rate=1))

        # Counters
        self._errorCounterPerTest={}
        self._CallErrorCounter=self.client.get_client(class_=Counter, name='CallErrorCounter')
        self._sessionCounter=self.client.get_client(class_=Gauge, name='sessionActive')


        # Gauge
        self.gauge=self.client.get_client(class_=Gauge, name='TPS')

        # timers hash
        self.timer_hash={}

    def __repr__(self):
        return '[host=%s][port=%s][testname=%s]' % (self.host, self.port, self.scenario_name)

    def __del__(self):
        print 'bye'

    def getClientLabel(self):
        return "Grinder"

    def getClientIdentifier(self):
        return "Grinder"

    def addNbStartedCount(self):
        self._StartedCounter+=1

    def addNbFinishedCount(self):
        self._FinishedCounter+=1

    def addNbCallCount(self, testname=None):
        pass

    def addNbCallErrorCount(self, testname):
        self._CallErrorCounter+=1

        if testname not in self._errorCounterPerTest:
            self._errorCounterPerTest[testname]=self.client.get_client(class_=Counter,
                                                                       name='%s.errorCounter' % (testname))

        self._errorCounterPerTest[testname].increment()

    def incrementSessions(self, sessionName=None):
        with self.sessionLock:
            self.sessionCount+=1
            self._sessionCounter.send(sessionName, self.sessionCount)

    def decrementSessions(self, sessionName=None):
        with self.sessionLock:
            self.sessionCount-=1
            self._sessionCounter.send(sessionName, self.sessionCount)

    def setConcurrentSessions(self, nbSessions):
        self._sessionCounter.send(self.source, nbSessions)

    def setTime2(self, deltaTime, actionName):
        '''
           :param deltatime: 
           :param actionName: what we want to monitor
        '''
        if actionName not in self.timer_hash:
            self.timer_hash[actionName]=self.client.get_client(class_=Timer, name=actionName)

        self.timer_hash[actionName].send(None, deltaTime)

    def setTime1(self, startActionTime, testName):
        '''
           :param deltatime: 
           :param actionName: what we want to monitor
        '''
        actionName='%s_gt_latency' % (testName)
        if actionName not in self.timer_hash:
            self.timer_hash[actionName]=self.client.get_client(class_=Timer, name=actionName)

        self.timer_hash[actionName].send(None, System.currentTimeMillis() - startActionTime)

    def setTPS(self, tps):
        self.gauge.send(None, tps)


if __name__ == "__main__":
    import time

    host, port='localhost', 8125
    a=StatsdClient(host, port)
    print "Connected to %s:%d!" % (host, port)

    for i in range(100):
        a.addNbStartedCount()
        a.startToken()
        startTime=System.currentTimeMillis()
        time.sleep(1.5)
        a.setTime1(startTime, '')
        a.endToken()
        a.addNbFinishedCount()
        a.addNbCallCount()

    time.sleep(300)
    print "Terminated"
