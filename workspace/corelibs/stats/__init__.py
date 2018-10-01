from corelibs.coreGrinder import CoreGrinder

logger=CoreGrinder.getLogger()
__all__ = ['ReporterBase']

class ReporterBase:

    def __init__(self, host, port, location):
        logger.debug('%s instantiated with host %s, port %s, location %s' % (self.__class__.__name__, host, port, location))
        self.scenario_name =  location or 'grinder'
        self.host=host
        self.port=port

    def addNbStartedCount(self):
        pass

    def addNbFinishedCount(self):
        pass

    def addNbCallCount(self, testname=None):
        pass
 
    def addNbCallErrorCount(self, testname):
        pass

    def incrementSessions(self, sessionName=None):
        pass

    def decrementSessions(self, sessionName=None):
        pass

    def setConcurrentSessions(self, nbSessions):
        pass
    
    def setTime1(self, startActionTime, actionName):
        pass

    def setTime2(self, startActionTime, actionName):
        pass

    def setTPS(self,tps):
        pass


 
