'''
   The core engine of grindertool
   Mercurial project : 
'''
from __future__ import with_statement

import atexit
from java.lang import Exception as JavaException, Thread
from java.lang import System
import sys
from threading import Condition, Lock
from threading import Event
import time
import traceback

from net.grinder.engine.process import ShutdownException
from net.grinder.script import Test
from org.slf4j import MDC

from corelibs.BaseConfiguration import BaseConfiguration
from corelibs.asynchronous import asynchronous
from corelibs.asynclog import asynclog
from corelibs.collector_proxy import proxy
from corelibs.configuration import Configuration
from corelibs.context import Context
from corelibs.contextCallback import HTTPServerCallback
from corelibs.contextIdentifier import ContextIdentifier
from corelibs.coreGrinder import CoreGrinder
from corelibs.macroLibs import CachedMacros
from corelibs.memory import MemoryMgr
from corelibs.grinderQueue import GrinderQueue
from corelibs.reporting import reporting
from corelibs.token import ContextToken, AbortRunToken, Token, ThroughputToken


properties=CoreGrinder.getProperty()
grinder=CoreGrinder.getGrinder()
logger=CoreGrinder.getLogger()

#--------------------------------------------------------------

# For custom logging
loggerProxy=proxy.getLoggerProxy()

# process static configuration
Configuration.initialize()

logger.info('===> configuration terminated <====')

class AsyncException(Exception):
    pass


@atexit.register
def bye():
    print ''
    print '.'*50
    print 'bye() - Stopping everything properly ...'    
    logger.info('bye() - Stopping everything properly ...')
    if Configuration.async:
        logger.info("Stopping the Async Http server ...")
        print 'Stopping the Async Http server ... (Graceful period of %d milliseconds)' % (Configuration.http_graceful_period)
        Thread.sleep(Configuration.http_graceful_period)
        HTTPServerCallback.stop()
        
    if Configuration.smpp_started:
        if Configuration.getSmscDriver():
            logger.info('Stopping the SMSCDriver (wait %d seconds) ...' % (Configuration.smpp_graceful_period))
            print('Stopping the SMSCDriver (wait %d seconds) ...' % (Configuration.smpp_graceful_period))
            time.sleep(Configuration.smpp_graceful_period)
            Configuration.getSmscDriver().stop()
    
    # If the contectIndentifier has been initialized then stop the reaper
    logger.info( "Stopping the ContextIdentifier Thread")
    ContextIdentifier.stop()
        
    # Reset TPS at the end
    if Configuration.use_reporter:
        Configuration.getClientReporter().setTPS(0)
        
    logger.info('bye() - END - All is terminated')
    print('bye() - END - All is terminated')
    
class TestRunner:

    
    # To synchronize startup
    thread_count=0
    event=Event()
    cv=Condition()
    activeSession=0
    controlSessionCount=0
    lockSession=Lock()
        
    def __init__(self):
        
        # A token is an event and a content
        self.token=None

        # Initialize macro & create a local copy
        self.macrosCached = CachedMacros().copyMacros()
        
        # immutable scenario list 
        self.scenarioList = Configuration.getScenarioList()
        
        # Memorization of previous calls 
        # memorization is a transient state - all results are stored in session Context()
        self.memoryManager = MemoryMgr(Configuration.dataFilePath)
        
        # Test executed initializations  
        self.testImpl={}
        self.__createTest()

        # Delay the reporting to console
        grinder.statistics.delayReports = 1        
                
        # monkey patching main acting thread
        self.__call__ = self.__rampup_call__
        
        # This is 
        if Configuration.thread_control_enable:
            self.__call__ = self.__controlled_rampup_call__
        
        # monkey patching
        if Configuration.pureThreadMode and not Configuration.waiting_mode:
            if Configuration.async:
                # PERFORMANCE THREAD MODE with asynchronous flows
                # This is not possible to work in that mode ...
                logger.error('Not supported use case: thread mode with asynchronous flows. Use Throughput mode instead.')
                raise NotImplementedError('Not supported use case: thread mode with asynchronous flows. Use Throughput mode instead.')
 
            self.__call__ = self.__direct_call__
        
        # Synchronize all threads for the throughput mode to avoid peaks effect
        if Configuration.use_throughput:
            self.__class__.__synchronize()                    
            
        if Configuration.use_reporter:
            # Force token_lag to 0 as this is a new test
            Configuration.getClientReporter().setTime1(System.currentTimeMillis(),'token_lag')
            # Reset TPS to zero
            Configuration.getClientReporter().setTPS(0)
            
            # Again optimization with monkey patching -:(
            self.__lanch_scenario__=self.__lanch_scenario_with_reporter__

    @classmethod
    def __synchronize(cls):
        '''
          Meeting point for all threads for ramping up mode and validation mode
        '''        
        if grinder.threadNumber==0:
            logger.info('Thread meeting point begin before ramp up() ...')
        
        cls.cv.acquire()
        cls.thread_count += 1
        cls.cv.release()
        
        if cls.thread_count == Configuration.numberOfThreads:
            logger.info('All threads are initialized - rampup can start')
            cls.event.set()
  
        # During the wait of other threads, initialize SMSC   
        if grinder.threadNumber==0:
            Configuration.waitAfterSMSC()
            
        # wait here until we get an event.set()
        cls.event.wait()

        # The thread 0 is responsible to start the Throughput threads
        if grinder.threadNumber==0:
            
            if Configuration.getMetronom():
                logger.info('>>> STARTING metronom !')
                Configuration.getMetronom().start()       

        if grinder.threadNumber==0:
            logger.info('Thread meeting terminated() ...')

    def __createTest(self):
        '''
          pre-creation of all test instrumentation for this local thread.
          please note that each protocol are initialized only one time
          --------------------------------------------------------------
          TODO: re-implement in a proper way ...
        '''
        if grinder.threadNumber == 0:
            logger.info('######### Initializing test ...')
        
        procNumber=Configuration.processNumber
        rangeTest=BaseConfiguration.testRangeSize
        if logger.isTraceEnabled():
            if grinder.threadNumber == 0 and Configuration.oneFileByProcess:
                logger.trace('CreateTest - [processNumber=%d][testRangeSize=%d]' % (procNumber, rangeTest))
        
        for scenario in self.scenarioList: 
            for line in scenario.get_array_lines():
                
                # always instantiate the protocol/implementation  
                self.testImpl[line.getTestId()] = line.getImplementation()(Configuration.dataFilePath, Configuration.templateFilePath)
                Test(line.getTestId(), line.getTestName()).record(self.testImpl[line.getTestId()].sendData)

                if logger.isDebugEnabled():
                    if grinder.threadNumber == 0:
                        logger.debug('Initialized test [scenarioId=%d][name=%s][testId=%d][testname=%s][implementation=%s] - object: %s' % (scenario.scenarioId,
                                                                                                        scenario.name, line.getTestId(), line.getTestName(), 
                                                                                                        line.getImplementation(), self.testImpl[line.getTestId()]))
        if grinder.threadNumber == 0:
            logger.info('######### Tests initialized ...')
       
        if not self.testImpl:
            logger.error('No tests were create ! Review your configuration')
            raise SyntaxError('No tests were create ! Review your configuration')
        
    def _processResponse(self, response, ctx):
        """
           process the response. Memorization and assertion processing.
        :param response: dictionary of response
        :param ctx: all the step context
        """
        try:
            # case errorCode is not defined or an empty string
            try:
                response['errorCode'] = int(response['errorCode'])
            except (KeyError, ValueError):
                logger.warn('"errorCode" not defined in implementation response, defaulting to 200 (success).')
                response['errorCode'] = 200
                
            # Breakdown asked in the implementation
            __break = response.get('breakdown', False)
            
            # errorCode is a functional error code, not a protocol one (like http status code)
            if response['errorCode'] not in (200, 0) or __break:
                return True, response.get('errorMessage','Error raised from the implementation - [errorCode=%d][breakdown=%s]'% (response['errorCode'], __break))
    
    
            ##### To follow & debug response output
            # TODO: could be overloaded by the Yaml scenario
            responseText = response.get('responseText', properties.get('grindertool.empty_response') or '*** responseText key is not defined ***')
            
            # print out the response but limited by default to the first 1024 characters
            max_len_debug = properties.getInt('grindertool.response.print.maxlen', 1024) 
            if logger.isInfoEnabled():
                logger.info('%s\nRESPONSE=\n%s\n%s' % ('-'*30, responseText[:max_len_debug],'-'*30))
                                
            if Configuration.displayReadResponse:
                print '>>>> %s\n' % (responseText[:Configuration.displayReadResponseMaxLength])
    
            # Memorization - must be done before assertion checking 
            if ctx.line.isMemorized():
                ctx.getCacheKeys().update_keys(response)
                if logger.isTraceEnabled():
                    logger.trace('Before memorization, current Step:\n %s' % str(ctx.line))
                self.memoryManager.memorizeVariable(ctx.line.getMemorizedValues(), responseText,
                                                    ctx.getCacheKeys().get())
    
                # (validation feature) an assertion comparison key could have be just memorized one
                ctx.getCacheKeys().update_keys_permanently(self.memoryManager.memorizedData)
                
                # This memorization was lost when we have fast async callback
                # Locks have been added to be sure theses memorization data will be available to next steps. 
                if ctx.line.isAsynchronous():
                    ContextIdentifier.update(ctx.contextKey, ctx.contextValue, self.memoryManager.memorizedData)

            # Check assertion on the response
            # No more using Yield (because of perf on error on Xpath )
            assertionFailed, _cause = ctx.line.checkResponse(response, ctx)
            if assertionFailed:
                if 'deviceId' in ctx:
                    _cause = '[deviceId=%s]%s' % (ctx['deviceId'], _cause)
                return True, _cause
        
        # SHOULD not happen - this means there is a problem in the scenario
        except KeyError, x:
            return True, 'Probably a poorly defined scenario, reason: %s' % x
        except Exception, x:
            # We cannot fails here, so we stop here with a fatal 
            x='%s\n while analyzing response [test=%s] [scenario=%s]' % (x, ctx.line.getTestName(), ctx.scenario)
            reporting.sendData_fatal(ctx,  x, response)                    
            raise SyntaxError(x)

        return False, 'No error'
            
    def _busyManagement(self, response):
        """
          flow regulation based on 503 errorCode
        :param response:
        """
        # Busy management 
        if response['errorCode'] == 503:
            if Configuration.use_regulator:
                Configuration.getMonitor().setBusyCount()
            else:
                logger.info('Got a Http-503 server busy response, printing context:\n\'\'\'%s\'\'\'' % response)

    def _sendData(self, __ctx):
        """
             Call the implementation
        :param ctx: current context
        """
        # process data for the current step
        submitCmd = __ctx.processNew()
        
        if logger.isTraceEnabled():
            logger.trace('[%s._senData()][testId=%d][testName=%s][data="%s"]' % (self.__class__.__name__,
                                                                                 __ctx.line.getTestId(),
                                                                                 __ctx.line.getTestName(),
                                                                                 str(submitCmd)))
            
        __ctx.line.do_step_sleep('before')    

        # Optimistic locking : we create the remote async context even if the implementation fails
        if __ctx.line.isAsynchronous():    
            try:
                jsonMsg = asynchronous.call_before(__ctx)
            except Exception, x:
                logger.error('Exception raised in asynchronous.call_before(): %s' % (x) )
                raise AsyncException(x)

        # Execute implementation - launch the test
        try:    
            startTime = System.currentTimeMillis()
            
            spResp = self.testImpl[__ctx.line.getTestId()].sendData(data=submitCmd, 
                                                                    context= __ctx.getCacheKeys().get(),
                                                                    testname= __ctx.line.getTestName(),
                                                                    memorizedFlag= __ctx.line.isMemorized(),
                                                                    lastTemplate= __ctx.line.getLastTemplate(),
                                                                    variables= self.memoryManager,
                                                                    reporter= Configuration.getClientReporter())
                
        # Python or Java errors that is the question ...
        except (Exception, JavaException), x:
                if isinstance(x, ShutdownException):
                    print 'bye() - Stopping ShutdownException ...'    
                    sys.exit(1)
                impErrorMsg = 'Implementation %s failed, reason: %s' % (__ctx.line.getImplementation(),x)
                logger.error(impErrorMsg)
                exc_type, exc_value, exc_traceback = sys.exc_info()
                errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))
                logger.error(errorMsg)
                print '!'*50
                print impErrorMsg    
                # traceback
                print errorMsg
                print '!'*50
                #
                if isinstance(x,JavaException):
                    raise Exception(x)
                raise
        finally:
            # Temporary, time already calculated in implementation
            try:
                logger.debug('Setting "grindertool.step.executionTime" for RT assertion ')
                if not 'grindertool.step.executionTime' in spResp:
                    spResp['grindertool.step.executionTime']=System.currentTimeMillis() - startTime
            except NameError:
                spResp=dict()
                spResp['grindertool.step.executionTime']=System.currentTimeMillis() - startTime
            if Configuration.use_reporter: 
                Configuration.getClientReporter().setTime1(startTime, __ctx.line.getTestName())
        
        # Post asynchronous call
        if __ctx.line.isAsynchronous():    
            try:
                asynchronous.call_after(__ctx, spResp, jsonMsg)
            except Exception, x:
                logger.error('Exception raised in asynchronous.call_after(): %s' % (x))
                raise AsyncException(x)
        
        # The sleep is set after the call_after() because the callback answer could be fast
        # and so the context not stored in ContextIdentifier()
        __ctx.line.do_step_sleep('after')

        logger.debug('Test [testId=%d] [testName=%s] executed' % (__ctx.line.getTestId(), __ctx.line.getTestName()))
      
        return spResp

    def process(self, ctx, startNewScenario=True):
        """
             Execute the main loop of plan test
               - the scenario loop (if we have a list of scenario in infile parameter)
               - the steps (line) inside a scenario
        :param ctx: all the step context data structure
        :param startNewScenario: if asynchronous, the value is False
        """
        continueScenario=True
            
        # SCENARIO list loop
        while continueScenario:
            
            # Not asynchronous = New scenario OR Async assertion error on previous scenario = New scenario
            if startNewScenario:
                ctx.getNextScenario() 
                
                # Memorization reset between scenario
                self.memoryManager.reset()
                                
                # There is no other scenario - we have to stop here            
                if not ctx.scenario:
                    logger.info('[state=StopAllScenario] Last scenario reached - run terminated' )
                    
                    loggerProxy.end_run('end run')
                    break
                logger.info('[state=StartScenario][scenario=%s][scenarioId=%d][async=%s]' % (ctx.scenario.getName(),ctx.indexScenario,ctx.scenario.isAsynchronous()))
                
                loggerProxy.start_scenario(ctx.scenario.getName())
                        
            # Reinit external async variables                            
            startNewScenario=True          
                        
            # SCENARIO STEPS loop
            while ctx.getNextLine():

                if logger.isInfoEnabled():
                    logger.info('\n' + '-' * 80 + '\n' + (
                        '{:02d}-{} {:02d}-{}'.format(ctx.indexScenario, ctx.scenario.getName(), ctx.line.getTestId(),
                                                     ctx.line.getTestName())).center(80) + '\n' + '-' * 80 + '\n')
                    logger.info('[state=StartStep] %s' % (reporting.localization(ctx)))
                if Configuration.displayReadResponse:
                    print '\n%s\n' % ('o' * 80)
                    print '{:02d}-{} {:02d}-{}'.format(ctx.indexScenario, ctx.scenario.getName(), ctx.line.getTestId(),
                                                       ctx.line.getTestName())
                    print '\n%s\n' % ('o' * 80)

                spResp={}
                errorOnThisStep=False

                try:

                    # Call implementation
                    spResp = self._sendData(ctx)
                    
                except SystemExit:
                    logger.info('SystemExit caught - a ShutdownException was raised')
                    break
                
                except (SyntaxError, KeyError) as x:
                    reporting.sendData_fatal(ctx,  x, None)                    
                    raise SyntaxError("%s\n while processing test '%s' in scenario '%s'" % (x, ctx.line.getTestName(),
                                                                                            ctx.scenario))
                    
                except Exception, cause:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    errorMsg=repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                    logger.error(errorMsg)
                    spResp['responseText']=str(cause)
                    errorOnThisStep=True
                                
                # Look for functional error in the response ( assertion checking )
                if not errorOnThisStep:               
                    errorOnThisStep, cause = self._processResponse(spResp, ctx)
                    
                # Step FAILURE
                if errorOnThisStep:
                    reporting.sendData_failure(ctx, str(cause), spResp) 
                    
                    # 
                    # An asynchronous step that fails cannot continue
                    #   - either because there is a 500
                    #   - either because an assertion reject it
                    # If we don't reject the async step, the following assertion step will check for unknown data
                    # --------------------------------------
                    #
                    if ctx.line.isAsynchronous() or Configuration.grinderStopScenarioOnError or ctx.line.stopOnError:
                        # TO NOT FORGET: releasing a scenario implies ignoring the promised async calls
                        # DON't CHANGE IT unless truly mastered !
                        if ctx.scenario.isAsynchronous():
                            asynchronous.manage_exception(ctx)
                        logger.debug('[state=StopScenarioKO] %s' % reporting.localization(ctx))
                        break
                    # Ok, we don't stop despite the step error
                    else:
                        logger.debug('[state=ContinueStepKO] %s' % reporting.localization(ctx))
                        
                # Step SUCCESS
                else:
                    # Server too busy (503) management
                    self._busyManagement(spResp)

                    reporting.sendData_success(ctx, spResp)
                    
                # if Asynchronous: check if we release the current Thread or not                   
                if asynchronous.manage_async_break(ctx):
                    break

            # Steps loop
            if not ctx.line:                              
                loggerProxy.end_scenario('finish')
                logger.info('[state=StopScenarioOK] [scenario=%s] No more step to be processed - exiting' %
                            ctx.scenario.getName())
      

    def processScenario(self):
        '''
           Launch a new run for one scenario or awake a sleeping one
        '''
        startNewScenario=True
        ctx=None
        dictCallingToken={}
        
        if self.token:
            # a restored context following a timeout or a callback processing failure
            if isinstance(self.token, Context):
                ctx=self.token
                # Special case : Timeout encountered is considered as a success
                if ctx.scenarioContinue:
                    startNewScenario=False
                    ctx.scenarioContinue=False
                MDC.put('uid','[uid=%s]' % (ctx.uid))
                logger.info('[state=ResumeScenarioKO] %s' %(reporting.localization(ctx)) )
                
            # Async callback context 
            elif isinstance(self.token,ContextToken):
                asynclog.log(pos='%s.processScenario' %(self.__class__.__name__), key=self.token.getContextKey(),value=self.token.getValue(), 
                                   msg='Getting a waiting token in a ContextToken')
                ctx=ContextIdentifier.pop_ctx_value(key=self.token.getContextKey(), value=self.token.getValue())
                    
                if ctx:
                    asynclog.log(pos='%s.processScenario' %(self.__class__.__name__), key=self.token.getContextKey(),value=self.token.getValue(), 
                                       msg='Found a waiting token',ctx=ctx  )
                    startNewScenario=False
                    # the awaken and updated context can be processed on following steps
                    abort = asynchronous.process_callback(ctx, self.token.getContextData())
                    if abort:
                        logger.info('[state=ResumeAsyncScenarioKO][key="%s"][value="%s"] %s' %(self.token.getContextKey(), self.token.getValue(),
                                                                                     reporting.localization(ctx)) )
                        return
                    logger.info('[state=ResumeAsyncScenario][key="%s"][value="%s"] %s' %(self.token.getContextKey(), self.token.getValue(),
                                                                                     reporting.localization(ctx)) )
                else:
                    # Waiting mode - we arrive without any context
                    if  GrinderQueue.waiting_mode:
                        # add what we get from the environment 
                        dictCallingToken={self.token.getContextKey():self.token.getValue()}
                        dictCallingToken.update(self.token.getContextData())
                        logger.info('[state=StartScenarioFromEvent] waiting_mode - Event token dictCallingToken=%s ' % (dictCallingToken))
                    else:
                        # We had a token and the token was not found ... not normal ... we must stop this run here
                        # TODO: create an error Test to store the error at the Test object level
                        logger.warn('[state=ResumeScenarioFailed] [timeout?] Context of type [%s], content: "%s" was not found' % (self.token.getContextKey(), 
                                                                                                                                  self.token.getValue()))
                        grinder.sleep(10)
                        return

        # Throughput, thread all mode                
        if not ctx:
            loggerProxy.start_run(Configuration.shortFileName)
            ctx=Context(self.macrosCached)    
            # waiting scenario started from external events        
            if dictCallingToken:
                ctx.cacheKeys.add_dynamic_keys(dictCallingToken)            
            logger.info('[state=StartNewScenarioList] [scenarioList=%s]' % (self.scenarioList))        

        # Process the scenario list
        try:
            self.process(ctx, startNewScenario)  
        except:
            logger.info('[state=StopScenarioKO] [scenario=%s] see stacktrace for information' % (ctx.scenario.getName() if ctx else 'NO CONTEXT') )
            raise              
        finally:
            MDC.remove('uid')

    def __checkTokenReceived(self):
        '''
           - return True if the RUN is aborted (async feature) or an explicit STOP RUN is triggered 
           - return False is the token is known or of "None" type ... the run continue
           
           Remark: Metronom explicit STOP RUN is done by poisoning the "Token" object with a negative "time_to_sleep" attribute
        '''
        
        if logger.isTraceEnabled():
            logger.trace('_processToken() - [type=%s] [token ="%s"]' % (  self.token.__class__.__name__,self.token))

        # To ignore so useless Runs due to not executed async calls 
        if isinstance(self.token, AbortRunToken):
            return True
        
        if isinstance(self.token, Token):
            # All token might be poisoned to stop processing properly
            if self.token.time_to_sleep <0:
                # grace period
                Thread.sleep(properties.getInt('sleep_before_death', 5000))
                logger.trace("Arghhh! - i have been poisoned !" )
                grinder.stopThisWorkerThread()        
                # No need to continue ...
                return True        
 
            # Batch mode implementation. Sleep time is done per consumer thread
            if isinstance(self.token, ThroughputToken) and self.token.wait:
                Thread.sleep(self.token.time_to_sleep)

        return False
                
#====================================================================================================================        
#  ALL the code entry point 
#====================================================================================================================        
    
    def __call__(self):
        logger.error('If i am called - there is a bad configuration')

    def __controlled_rampup_call__(self):
        '''
           Attempt to control thread starvation 
        '''

        # Block or not (depending of the configuration)
        self.token=GrinderQueue.take()       

        # Token means we are using ramping mode (no thread mode)
        if self.token:
            # check abort, stop and options set on token (sleep for batch mode)
            if self.__checkTokenReceived():                
                return

        try:
            
            # Increase the number of active session for this process
            with self.__class__.lockSession:
                self.__class__.activeSession+=1
                logger.trace('[CONTROL] active sessions: %d' % (self.__class__.activeSession))
                
                # if number of active session is above a configurable threshold
                #  - clear the current waiting operation 
                #  - sleep a bit to let some breath 
                if  self.__class__.activeSession >= Configuration.threshold_thread_active:
                    
                    self.__class__.controlSessionCount+=1
                    logger.info('[CONTROL] Active sessions (%d) above threshold (%d) - clearing waiting tokens ' % (self.__class__.activeSession, Configuration.threshold_thread_active))
                    
                    # Clear the queue
                    GrinderQueue.clear()
                    
                    # Block all inactive thread (normally none or a few)   
                    Thread.sleep(Configuration.thread_wait_milli)
                    
                    # return here execute the finally part.
                    return

            # The real work is done here ...
            self.__lanch_scenario__()
            
        # Release the active session counter in ANY case
        finally:       
            with self.__class__.lockSession:
                self.__class__.activeSession-=1
                logger.trace('[CONTROL] active sessions: %d' % (self.__class__.activeSession))

    def __rampup_call__(self):
        '''
           Rampup call have throughput pace synchronized over a Token Queue() 
        '''
        
        # Block or not (depending of the configuration)
        self.token=GrinderQueue.take()       

        # Token means we are using ramping mode (no thread mode)
        if self.token:
            # check abort, stop and options set on token (sleep for batch mode)
            if self.__checkTokenReceived():                
                return

        # The real work is done here ...
        self.__lanch_scenario__()

    def __direct_call__(self):
        '''
           This is the pure thread mode.
           This replace __call__ by a monkey patching
        '''
        # Smooth ramp up based on thread number 
        # TODO: add group of threads using a modulo number 
        if Configuration.initialSleepTime != 0: 
            sleepTime = float(grinder.threadNumber) * Configuration.initialSleepTime
            time.sleep(sleepTime)
            logger.debug("initial sleep complete, slept for %d seconds" % (sleepTime))
        
        # Direct launch scenario
        self.__lanch_scenario__()

    def __lanch_scenario__(self):
            
        # Here, begins really the Yaml scenario execution        
        self.processScenario()           

    def __lanch_scenario_with_reporter__(self):

        # When a token is added in the Grinder token queue, it is marked with its arrival time
        # So the statistics here gives the lag before being consumed by a thread
        if self.token:
            Configuration.getClientReporter().setTime1(self.token.getTimestamp(),'token_lag')
        
        Configuration.sessionIncrement()
    
        # Here, begins really the Yaml scenario execution       
        try: 
            self.processScenario()           
        finally:       
            Configuration.sessionDecrement()