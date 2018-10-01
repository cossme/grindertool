'''
Created on 31 juil. 2014

@author: omerlin
'''
from java.lang import Thread
import time

#
from corelibs.cadencer import FlatCadencer

#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

class Monitor:
    '''
      a monitor simply control the cadencer object throughput
      if setBusyCount is called , the cadencer is slowed down
      otherwise the cadencer increase regularly its throughput level.
      whenever an event of busy is detected the incresy capacity is limited.
      
      The cadencer object is shared by:
        - the Monitor instance
        - the Metronom instance
        - The grinderTool main worker and all worker threads thru the global declaration
    '''
    monitorCounter=0
    def __init__(self, tpsInit, props, debug=False):
        self.debug=debug
        self.cadencer=FlatCadencer(tpsInit)
        self.busyCount=0
        self.maxTPS=int(props.get('regulatorMaxTPS'))
        self.initialTPS=int(props.get('regulatorInitialTPS'))
        self.busyStateInterval=int(props.get('busyStateInterval') or 60)
        self.tpsDecreaseAfterBusy=float(props.get('tpsDecreaseAfterBusy') or 0.2)
        self.quietPeriodInterval=int(props.get('quietPeriodInterval') or 60)
        self.quietPeriodFactor=float(props.get('quietPeriodFactor') or 2)
        self.tpsIncreaseAfterQuiet=float(props.get('tpsIncreaseAfterQuiet') or 0.1)       
        self.t = Monitor.__Control(self).start()
        self.cadencer.set(self.initialTPS)
        if self.debug:
            print 'Monitor is started ...'
        
    def __repr__(self):
        return 'busyStateInterval=%d\ntpsDecreaseAfterBusy=%3.1f\nquietPeriodInterval=%d\nquietPeriodFactor=%d\ntpsIncreaseAfterQuiet=%3.1f' % (self.busyStateInterval,self.tpsDecreaseAfterBusy,
                                                                       self.quietPeriodInterval,self.quietPeriodFactor,self.tpsIncreaseAfterQuiet)
    @staticmethod
    def setBusyCount():
        Monitor.monitorCount+=1

    @staticmethod
    def getBusyCount():
        return  Monitor.monitorCount
    
    @staticmethod
    def resetBusyCount():
        Monitor.monitorCount=0
            
    class __Control(Thread):
        def __init__(self,this):
            self.this=this
            self.busyFlag=False
            self.debug=self.this.debug
                        
        def run(self):
            clockBusyMarker=None
            quietPeriodMarker=None
            countQuiet=0
            initialQuietPeriodInterval=self.this.quietPeriodInterval
            maxReached=False
            while True:
                    
                if self.this.busyCount>0:
#                    if self.debug:
#                        print 'Monitor - busy period'
                    # process busy server
                    countQuiet=0
                    if self.busyFlag:
#                        if self.debug:
#                            print 'Monitor - busy flag - waiting for reseting busy counter ...'
                        if (time() - clockBusyMarker)> self.this.busyStateInterval:
                            if self.debug:
                                print 'Monitor - Busy state reset'
                            self.this.resetBusyCount()
                            self.busyFlag=False
                    else: ### busyFlag
                        #### WE ARE BUZY !!! ###
                        quietPeriodMarker=None
                        if self.debug:
                            print '[%s] Monitor - Busy state detected - current throughput=%3.1f' % ( time.strftime("%d/%m/%Y %H:%M:%S", time.localtime()),
                                                                                                      self.this.cadencer.getTps()) 
                        clockBusyMarker=time()
                        self.busyFlag=True
                        newTps=self.this.cadencer.getTps()-self.this.tpsDecreaseAfterBusy
                        if newTps<=0:
                            newTps=0.1 
                        self.this.cadencer.set(newTps)
                        if maxReached:
                            maxReached = False
                        self.this.quietPeriodInterval *= self.this.quietPeriodFactor
                        logger.debug('New thoughput = %3.1f, quiet period is now: %d' % (newTps,self.this.quietPeriodInterval ))
                #
                # quiet server : we increase pressure 
                #   
                else:
                    if not maxReached:
                        if quietPeriodMarker:
                            if  (time()-quietPeriodMarker)>self.this.quietPeriodInterval:                                
                                newTps=self.this.cadencer.getTps()+self.this.tpsIncreaseAfterQuiet
                                
                                #
                                # We decrease to quickly, so we return back to the initial TPS
                                # and we reinitialize the quiet period interval to its initial value
                                #
                                if countQuiet>10 and self.this.cadencer.getTps()<self.this.initialTPS:
                                    newTps=self.this.initialTPS
                                    countQuiet=0
                                    self.this.quietPeriodInterval = initialQuietPeriodInterval
                                
                                if newTps > self.this.maxTPS:
                                    maxReached=True
                                    logger.debug('Monitor - max TPS [%3.1f] reached' % (self.this.maxTPS))
                                else:    
                                    self.this.cadencer.set(newTps)
                                    logger.debug('Monitor - QuietPeriod [%d]: Increasing throughput to: %3.1f ' % (self.this.quietPeriodInterval, newTps ))
                                
                                quietPeriodMarker=None
                                    
                        else:
                            if self.debug:
                                print 'Monitor - Starting quiet period ...'
                            quietPeriodMarker=time()    
                            countQuiet+=1
                
                Thread.sleep(100) 
        
