'''
@author: tboher
'''
from corelibs.coreGrinder import CoreGrinder
from corelibs.stats import ReporterBase
logger=CoreGrinder.getLogger()

class DummyReporter(ReporterBase):
    
    def __init__(self, host, port, location):
        ReporterBase.__init__(self, host, port, location)
        print ('DummyReporter instantiated')
        logger.debug('DummyReporter instantiated')
        
    def addNbCallCount(self, testname=None):
        print ('DummyReporter addNbCallCount called.')
        logger.debug('DummyReporter addNbCallCount called.')
 
    def addNbCallErrorCount(self, testname):
        print ('DummyReporter addNbCallErrorCount called.')
        logger.debug ('DummyReporter addNbCallErrorCount called.')

    def incrementSessions(self, sessionName=None):
        print ('DummyReporter incrementSessions called.')
        logger.debug ('DummyReporter incrementSessions called.')

    def decrementSessions(self, sessionName=None):
        print ('DummyReporter decrementSessions called.')
        logger.debug ('DummyReporter decrementSessions called.')

    def setTime1(self, startActionTime, actionName):
        print ('DummyReporter setTime1 called startActionTime[%s], actionName[%s].' % (startActionTime, actionName))
        logger.debug('DummyReporter setTime1 called startActionTime[%s], actionName[%s].' % (startActionTime, actionName))

    def customMethod(self, gruck=None):
        print ('DummyReporter customMethod called gruck[%s].' % gruck)
        logger.debug('DummyReporter customMethod called gruck[%s].' % gruck)
