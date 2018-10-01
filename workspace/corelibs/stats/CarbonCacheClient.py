'''
Created on Sep 9, 2010

@author: omerlin, wgoesgen
'''
from java.lang import System, Thread
from java.text import NumberFormat
import socket
from threading import Lock
import time


class CarbonCacheClient:
    def __init__(self, host, port, scenario_name=None):
        self.scenario_name=scenario_name
        self.host=host
        self.port=port
        self.sharedInstance = None
        self._numberFormat = NumberFormat.getInstance()
        self._numberFormat.setMinimumFractionDigits(1)
        self._numberFormat.setMaximumFractionDigits(3)
        self._nbCallSuccessSoFar = 0
        self._nbCall = 0
        self._nbCallError = 0
        self._nbCallErrorSoFar = 0;
        self._nbCall_tps = 0
        self._injection_rate = 0
        self._sumTime = 0
        self._maxTime = 0
        self._lastRefresh = System.currentTimeMillis()
        self.CarbonCache = Thread(CarbonCacheClient.__AggregateReportThread(self, host, port), "TheCarbonCache")
        self.CarbonCache.start()

    def __repr__(self):
        return '[host=%s][port=%s][testname=%s]' % (self.host,self.port, self.scenario_name)

    class __AggregateReportThread(Thread):
        def __init__(self, Reporter, host, port):
            self.Reporter = Reporter
            self.socket = socket.socket()
            try:
                self.socket.connect((host, port))
            except:
                print "unable to connect to Carbon Cache on %s Port %s" %(host, port)
                raise

            def __del__(self):
                self.socket.close()

        def run(self):
            while True:
                timestamp = int(time.time())
                OneMessageSet = ""
                Thread.sleep(10000)
                ReportSet = self.Reporter.GetReportStructured ()
                for ValueName in ReportSet:
                    message = "%s.%s %s %d\n" % (self.Reporter.getClientIdentifier(),
                                                 ValueName,
                                                 ReportSet[ValueName],
                                                 timestamp)
                    OneMessageSet += message

                self.socket.sendall(OneMessageSet)
        
    def getClientLabel(self):
        return self.scenario_name or "grindertool"

    def getClientIdentifier(self):
        return self.scenario_name or "grindertool"
        
  
    def GetReportStructured(self):
        currentTime = System.currentTimeMillis()
        deltaTime = (currentTime - self._lastRefresh)
        NbCall_tps = 0.0
        avgTime=0.0
        maxTime=0.0

        if (deltaTime > 0):
            NbCall_tps = float(self._nbCall_tps * 1000) / deltaTime
            avg=0
            if self._nbCall_tps > 0:
                avg = long(self._sumTime / self._nbCall_tps)
            avgTime = avg
            maxTime = self._maxTime
        else:
            NbCall_tps = 0
            avgTime = 0
            maxTime = 0

        self._maxTime = 0

#         NowRunning = self._nbStarted - self._nbFinished
# 
#         DeltaStarted = self._nbStarted - self._nbStartedTotal
#         self._nbStartedTotal = self._nbStarted
# 
#         DeltaStopped = self._nbFinished - self._nbStoppedTotal
#         self._nbStoppedTotal = self._nbFinished

        DeltaSuccess = self._nbCall - self._nbCallSuccessSoFar
        self._nbCallSuccessSoFar = self._nbCall

        DeltaError = self._nbCallError - self._nbCallErrorSoFar
        self._nbCallErrorSoFar   = self._nbCallError

        Reply = {
            "Cadence.InjRate"  : "%f" % (self._injection_rate),
#             "Session.Started"  : "%d" % (DeltaStarted),
#             "Session.Finished" : "%d" % (DeltaStopped),
            "Session.Running"  : "%d" % (self._nbRunningSessions),
            "NbCall.Success"   : "%d" % (DeltaSuccess),
            "NbCall.Error"     : "%d" % (DeltaError),
            "NbCall.tps"       : "%f" % (NbCall_tps),
            "Time.Avg"         : "%f" % (avgTime),
            "Time.Max"         : "%f" % (maxTime)
            }

        self._lastRefresh = currentTime;

        return Reply

    def addNbStartedCount(self):
        self._nbStarted+=1

    def addNbFinishedCount(self):
        self._nbFinished+=1
  
    def addNbCallCount(self):
        self._nbCall+=1
        self._nbCall_tps+=1

    def addNbCallErrorCount(self):
        self._nbCallError+=1

    def setTime1(self, startTime, TimerName):
        NowTime = System.currentTimeMillis()
        lock=Lock()
        lock.acquire()
        duration=NowTime-startTime
        self._sumTime += duration
        if duration>self._maxTime:
            self._maxTime = duration
        lock.release()

    def setTPS(self,tps):
        self._injection_rate=tps
        
    def incrementSessions(self):
        self._nbRunningSessions +=1

    def decrementSessions(self):
        self._nbRunningSessions -=1
        
    def setConcurrentSessions(self, nbSessions):
        self._nbRunningSessions =  nbSessions



if __name__ == "__main__":
    a = CarbonCacheClient('127.0.0.1', 8051)  
    print "Connected !"

    for i in range(100):
        a.addNbStartedCount()
        time.sleep(5)
        a.addNbFinishedCount()
        a.addNbCallCount()

    time.sleep(300)
    print "Terminated"
    
    
