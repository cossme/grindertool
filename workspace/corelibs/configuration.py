'''
Created on 23 sept. 2014

@author: omerlin
'''

from __future__ import with_statement

from itertools import imap
from java.lang import Exception as JavaException
import os
import socket
from threading import Condition
import time

# Bootstrap libraries
from corelibs.coreGrinder import CoreGrinder

from corelibs import command
from corelibs.contextCallback import HTTPServerCallback
from corelibs.contextIdentifier import ContextIdentifier
from corelibs.contextRouterClient import ContextRouterClient
from corelibs.metronom import Metronom
from corelibs.monitor import Monitor
from corelibs.grinderQueue import GrinderQueue
from corelibs.scenarioList import  ScenarioList
from corelibs.stats.CarbonCacheClient import CarbonCacheClient
from corelibs.stats.CentralReporterClient import CentralReporterClient
from corelibs.stats.StatsdClient import StatsdClient
import toolbox
from corelibs.contextLock import ContextLock

grinder=CoreGrinder.getGrinder()
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()


try:            
    from corelibs.SmscDriver import SMSCDriver
except ImportError, e:
    if properties.getBoolean('grindertool.smsc.start', False):
        logger.error('FATAL - are the libraries located in grindertool.smsc.libs loaded ?')
        raise e


class Configuration:
    
    # Some required declaration
    dataFilePath = properties.get('dataFilePath')
    templateFilePath = properties.get('templateFilePath')
    cmdMgr = None
    
    outTraceActivated = False
    fOut = None
    fOutExtra = None
    cv_out = None
    cv_ext = None
    extraLevel=False
    
    # get the delay time between commands
    interMessageDelay = properties.getDouble('messageDelay', 0.0)
    initialSleepTime = properties.getDouble('grinder.initialSleepTime', 0.0)

    #
    # because it is possible that each process (and therefore, each test_thread)
    # could be kicked off numerous times by the console without exiting, get the total number of threads
    # and processes, then modulo divide the process and test_thread number with the total (respective) number
    # this will correctly create the correct file name (file.X.Y) on multiple runs
    #
    numberOfThreads = properties.getInt('grinder.threads', 0)
#     numberOfRuns = properties.getInt('grinder.runs', 0)
    asyncruns=0
    numberOfProcess = properties.getInt('grinder.processes', 0)

    # When relaunching several times, the process number is incremented
    processNumber=CoreGrinder.getRealProcessNumber()    

    processNumberPadding=properties.getInt('processNumberPadding', 2)
    threadNumberPadding=properties.getInt('threadNumberPadding', 4)
    runNumberPadding=properties.getInt('runNumberPadding', 7)

    # ID format never changes, retrieve it once and for all.
    idFormat = toolbox.getidFormat()
    processIdFormat='%%0%dd' % (processNumberPadding)
    runIDPadding=toolbox.getRunIDPadding()
    runIdFormat='%%0%dd' % (runNumberPadding)
    threadIdFormat='%%0%dd' % (threadNumberPadding)

    grinderStopScenarioOnError = properties.getBoolean('stop.scenario.on.error', properties.getBoolean('stopOnError', True))    
     
    #
    # if displayReadResponse is set to 'True', then display:
    #    the first 256 bytes of the response received from the command
    #
    displayReadResponse = properties.getBoolean('displayReadResponse', False)
    displayReadResponseMaxLength=properties.getInt('displayReadResponseMaxLength', 1024)
 

    # The way inFile (scenario) are set to process, thread for different UC processing
    oneFileByThread  = properties.getBoolean('oneFileByThread', properties.getBoolean('grindertool.test.scenarioPerThread', False))
    oneFileByProcess = properties.getBoolean('oneFileByProcess', properties.getBoolean('grindertool.test.scenarioPerProcess', False))
    
    oneSingleList=not ( oneFileByProcess or oneFileByThread)
    
    shortFileName = properties.get('grinder.console.propertiesFile') or ''
    if shortFileName:
        shortFileName = shortFileName.split(os.sep)[-1]   

    cacheProtocols = properties.getBoolean('cacheProtocols', False)
        
    # For Asynchronous management
    async=False 
    routerContextClient=None             

    # Http server callback for asynchronous flows 
    http_graceful_period=properties.getInt('grindertool.http.stop.graceful',5000)
        
    async=False
    pureThreadMode=False
    validationMode=False
    scenarioList=None
    waiting_mode=False

    # SmscDriver start if required
    smpp_started=properties.getBoolean('grindertool.smsc.start', False)
    # graceful period before stopping Smsc server (5 seconds by default)
    smpp_graceful_period=properties.getInt('grindertool.smsc.stop.graceful',5)
    smscDriver=None

    use_reporter=properties.getBoolean('reporter_activate', False)
    clientReporter=None

    metronom=None
    monitor=None
    use_throughput=properties.getBoolean('throughput_activate', False)
    if numberOfThreads==1:
        properties.setBoolean('throughput_activate', False)
        use_throughput=False
    use_regulator=properties.getBoolean('regulator_activate', False)
    
    listener_host='localhost'
    listener_port=9080
    listener_poolSize=32
    listener_socketBacklog=1024

    # TODO
    #-----------
    #  Add the grinder.threads as a Gauge
    #  Add the thread maximum from the parameter grindertool.threads.threshold_pct_active if thread_control_enable=True
    #
    
    # Active Session throttling 
    thread_control_enable=False
    threshold_thread_active=100
    thread_wait_milli=10
    
    
    @classmethod
    def initialize(cls):
        logger.info("********************* STARTING INITIALIZATION ***********************")
        
        # Check some parameters
        cls.checkParameters()       
        
        # Immutable scenario loading and flags relative to the different mode
        cls.manageScenarioAndFlags()
               
        # Asynchronous configuration
        if cls.async:
            cls.__manageAsyncConfiguration() 
 
            # Asynchronous callback listener - must be started after the asynchronous configuration
            cls.__startListener()
       
        # Initialize the SMSCToolkit and wait after connection only for pureThreadMode
        cls.__manageSMSCToolkit()         
        
        # Reporting monitoring data 
        cls.__manageClientReporter()

        # Ramping up mode management & flow controller mode
        cls.manageThroughput()        
        
        # thread throttling
        cls.activateSessionThrottler()
                
        logger.info("********************* END OF INITIALIZATION ***********************")
            
            

    @classmethod
    def activateSessionThrottler(cls):
        
        # This is a throughput throttling mechanism
        #----------------------------------------------------- 
        #   Threshold of active threads
        # thread throttling enable (True/False)
        cls.thread_control_enable=properties.getBoolean('grindertool.threads.control_enable',False)
        if cls.thread_control_enable:
        
            cls.threshold_thread_active=int( (properties.getInt('grindertool.threads.threshold_pct_active',100) or 100)/100)*cls.numberOfThreads
            if cls.threshold_thread_active> cls.numberOfThreads:
                raise SyntaxError('Number of threshold thread (%d) cannot be above number of grinder threads (%d)' % (cls.threshold_thread_active, cls.numberOfThreads))
            #   When over threshold, time sleeping doing nothing
            cls.thread_wait_milli=properties.getInt('grindertool.threads.sleep',10)
            
            logger.info('[CONTROL] Switching to controlled rampup ( [Threshold=%d][Threads=%d][Sleep=%d]  ) ...' % (cls.threshold_thread_active, cls.numberOfThreads, cls.thread_wait_milli))
            print ( '\t[CONTROL] Switching to controlled rampup ( [Threshold=%d][Threads=%d][Sleep=%d]  ) ...' % (cls.threshold_thread_active, cls.numberOfThreads, cls.thread_wait_milli))


    @classmethod
    def checkParameters(cls):

        # TODO : should be part of the scenario immutable object
        # The template (payload) manager is a global instance
        cls.cmdMgr = command.TemplateManager(cls.templateFilePath)
        
        # Output trace for validation
        cls.outTraceActivated = properties.getBoolean('outTraceActivated', False)
        if cls.outTraceActivated:
            outFile='%s%s%s.%s' % (properties.get('logFilePath') or cls.dataFilePath, os.sep,
                                   properties.get('fileout') or 'default', toolbox.getFileTimeStamp())
            cls.fOut = file(outFile, 'w')
            logger.info('outFile "%s"' % outFile)
            cls.extraLevel = properties.getBoolean('extraLevel',False)
            if cls.extraLevel:
                cls.fOutExtra = file('%s.EXTRA' % outFile, 'w')
                logger.info('outExtraFile "%s"' % cls.fOutExtra)
            # file lock for output and extra logging files
            cls.cv_out = Condition()
            cls.cv_ext = Condition()
        

    @classmethod
    def manageThroughput(cls):

        # Throughput mode
        logger.info('Throughput_mode: %s'  % (str(cls.use_throughput)))
        if (cls.use_regulator):
            cls.use_throughput=True
            Configuration.__launchRegulator(cls.clientReporter)
        else:
            # Thoughtput mode
            if cls.use_throughput:
                Configuration.__launchMetronom()
                properties.setInt('grinder.runs', 0)
    
        if cls.use_throughput:
            logger.info('[throughput_mode activated, so forcing parameter grinder.runs=0')
            properties.setInt('grinder.runs',0)
            if cls.numberOfThreads <16:
                logger.info('[throughput_mode activated, number of threads [current=%d] should be at at least greater than 16, setting to 16' % (cls.numberOfThreads))
                properties.setInt('grinder.threads',16)


    @classmethod
    def manageScenarioAndFlags(cls):

        cls.scenarioList = ScenarioList(cls)
        cls.async=cls.scenarioList.isAsync()
     
        # ValidationMode : in that case, the thread wait after the asynchronous operation termination 
        if cls.async:
            if cls.numberOfThreads==1 or cls.oneFileByThread or properties.getBoolean('grindertool.forceValidationMode',False):
                cls.validationMode=True
                cls.use_throughput=False

        cls.graceful_async=0
        if cls.async:
            cls.graceful_async=properties.getInt('grindertool.graceful_async_time',5000)
        
        # optimization for pure threading mode
        cls.waiting_mode=properties.getBoolean('waiting_mode', False)
        cls.pureThreadMode=not cls.use_throughput and not cls.async
        logger.info('FLAGS [async=%s][waitingMode=%s][throughput=%s][pureThreadMode=%s][validationMode=%s]' % (cls.async, cls.waiting_mode, cls.use_throughput, cls.pureThreadMode,cls.validationMode))
        
        # initialize static boolean variable
        GrinderQueue.setFlags(validationMode=cls.validationMode,pureThreadMode=cls.pureThreadMode,async=cls.async, 
                              throughput=cls.use_throughput, waiting_mode=cls.waiting_mode, graceful_async=cls.graceful_async)
        
        if cls.use_throughput and cls.waiting_mode:
            print '='*50
            print 'Throughput mode and waiting mode are incompatible, please review your configuration'
            print '\t change parameters: throughput_activate and waiting_mode'
            print '='*50
            logger.error('Throughput mode and waiting mode are incompatible. See documentation.')
            raise NotImplementedError('Throughput mode and waiting mode are incompatible. See documentation.')                    
        
        # Check parameters consistency
        if not cls.use_throughput and not cls.validationMode and cls.async:
            print '='*50
            print ' Thread mode with asynchronous flows is ** NOT supported **'
            print '\t please reconfigure your test to use the throughput mode'
            print '\t throughput_activate=true and options:'
            print '\t\t throughput_method - the rampup method  (optional, defaulted to RAMPING)'
            print '\t\t throughput_rampup - the rampup definition, for example 1,60 2,60 (1 TPS during 1minute, 2TPS during 2 minutes)'
            print '='*50
            logger.error('Thread mode cannot be used with asynchronous flows. It could be possible only if validation mode is enabled. See documentation.')
            raise NotImplementedError('Thread mode cannot be used with asynchronous flows. It could be possible only if validation mode is enabled. See documentation.')        

    @classmethod
    def waitAfterSMSC(cls):
        # We wait after SMSC driver connection
        if cls.smpp_started:
            logger.info('Waiting after SMSC')
            while not cls.getSmscDriver().isConnected():
                time.sleep(1)
            logger.info('*** SMSCDriver connected ...')

    @classmethod
    def __manageSMSCToolkit(cls):
        if Configuration.smpp_started:
            
            # The session callback hash storage
            if not ContextIdentifier.threadStarted:
                ContextIdentifier.start()
                logger.info('[async] Asynchronous Context queue identifier started')
                            
            smpp_profile=properties.get('grindertool.smsc.profile')
            
            if not smpp_profile:
                smpp_profile=properties.get('grindertool.smsc.profile.%d' % (cls.processNumber))
                
            if not os.path.exists(smpp_profile):
                raise SyntaxError('smpp configured for starting [smpp_start=true] but profile directory %s not found' % (smpp_profile))
            
            Configuration.smscDriver = SMSCDriver(smpp_profile)
            logger.info('SMSCDriver started but not still connected ...')     
            
            # if we have a pure thread mode that uses a SMSCToolkit
            if cls.pureThreadMode :
                cls.waitAfterSMSC()
                 
 
    @classmethod
    def __startListener(cls):
        
        # Callback async listener starting
        #----------------------------------
        cls.listener_port=9080 + grinder.agentNumber*100 + (grinder.processNumber - grinder.firstProcessNumber)
        cls.listener_host=properties.getProperty('grindertool.callback.host','localhost')
        cls.listener_port = properties.getInt('grindertool.callback.port',cls.listener_port)
        cls.listener_poolSize=properties.getInt('grindertool.callback.poolsize',32)
        cls.listener_socketBacklog=properties.getInt('grindertool.callback.socketBacklog',1024)
        HTTPServerCallback.initialize(cls.listener_host, cls.listener_port, cls.listener_poolSize, cls.listener_socketBacklog)
        HTTPServerCallback.start()
        logger.info('[async] Callback listener started on %s %d' % (cls.listener_host,cls.listener_port))
        msg='[async] Callback listener started:'
        print msg
        print '-'*len(msg)
        print '\tAsynchronous Callback listener started on %s %d\n' % (cls.listener_host,cls.listener_port)
        

    @classmethod
    def __manageAsyncConfiguration(cls):
        # Asynchronous thread server start
        logger.info('At least one scenario is asynchronous. [Async callback router usage=%s]' % (cls.scenarioList.isUsingContextManager()))         
        
        # The session callback hash storage
        if not ContextIdentifier.threadStarted:
            ContextIdentifier.start()
            logger.info('[async] Asynchronous Context queue identifier created')
        
        if cls.scenarioList.isUsingContextManager():               

            # contextManager client - async callback router client
            #-------------------------------------------------------  
            hostRouter=properties.get('grindertool.routerHost') or '127.0.0.1'
            portRouter=properties.getInt('grindertool.routerPort', 8080) 
            cls.routerContextClient = ContextRouterClient(hostRouter, portRouter)
            logger.info('[asyc] routerContextclient started, targeting %s %d' % (hostRouter, portRouter))
            
            # ping the context Manager
            try:
                cls.routerContextClient.ping()
                logger.info('[async] ping of the asynchronous callback router succeeded')
            except:
                print( 'Incorrect configuration for asynchronous call')
                print('\t... check contextManager is started at the right host, port')
                print('\t... current configuration:')
                print('\t\t... grindertool.routerHost: %s'% (hostRouter))
                print('\t\t... grindertool.routerPort: %d'% (portRouter))
                logger.error('[Ping failed] Incorrect async configuration, check contextManager configuration - see above')
                raise SyntaxError('[Ping failed] Incorrect async configuration, check contextManager configuration - see above')

        # Special case ... the last step of the last scenario is marked Async ... this is normally incorrect
        if cls.scenarioList.getLastScenario().isLastStepAsync():
            logger.error('Last Step of Last scenario COULD not be asynchronous! please add at least a dummy step after')
            logger.error('We cannot finish the whole test plan on an ASYN step !!')
            raise SyntaxError('Last Step Asynchronous on last scenario is REFUSED - please add at least a dummy step')
        
        # (Validation needs) Force another thread run if an async
        # VIRTUALRUN DEFINITION #                 
        cls.asyncruns=properties.getInt('grinder.runs',1)* ( 1 + cls.scenarioList.getAsyncStepsCount() )
        properties.setInt('grinder.runs', cls.asyncruns)
        grinder.getProperties().setInt('grinder.runs', cls.asyncruns)
        logger.info('<<ASYNC>> Setting the number of runs to %d' % (cls.asyncruns))
        ContextLock.setAsyncRuns(cls.asyncruns)
        
        msg='[async] scenario started:'
        print msg
        print '-'*len(msg)
        if cls.scenarioList.isUsingContextManager():
            print '\tAsynchronous Callback listener started on %s %d' % (cls.listener_host,cls.listener_port)
            print '\t\tgrindertool.callback.poolsize: %d' % (cls.listener_poolSize)
            print '\t\tgrindertool.callback.socketBacklog: %d' % (cls.listener_socketBacklog)
            print '\trouterContextclient started, targeting %s %d' % (hostRouter, portRouter)
        print '\t[NumberOfRuns=%d][ValidationMode=%s][throughputMode=%s]' % (cls.asyncruns, cls.validationMode, cls.use_throughput )
        print

    @classmethod
    def getScenarioList(cls):
        return cls.scenarioList.getList()
    
    @classmethod
    def __launchMetronom(cls):
        throughput_profile=None
        throughput_method=properties.get('throughput_method') or 'RAMPING'
        
        if cls.oneFileByProcess:
            logger.debug( '===> OneFileByProcess activated !!!')
        
        if  cls.oneFileByProcess and cls.numberOfProcess>=1:
            logger.debug('===> processNumber=%d/%d' % (cls.processNumber, cls.numberOfProcess))
            
            # ------------
            if properties.getBoolean('throughput_use_percentage',False):
                percent=0

                # Number of agent is required to have a repartition on several agent/machine
                agents=properties.getInt('grinder.agents',1)
                
                if grinder.agentNumber+1>agents:
                    logger.error('The number of agent [agentNumber=%d] exceed the parameter [grinder.agents=%d]' % (grinder.agentNumber+1, agents))
                    raise SyntaxError('The number of agent [agentNumber=%d] exceed the parameter [grinder.agents=%d]' % (grinder.agentNumber+1, agents))
                
                #
                target_KPI=properties.get('target_KPI') or None
                if target_KPI:
                    logger.info('property target_KPI=%s' % (target_KPI))
                if not target_KPI:
                    try:
                        target_KPI=','.join([properties.get('target_KPI%d' % (k)) for k in range(0, cls.numberOfProcess)])
                        logger.info('Created a target_KPI="%s" string from properties' % (target_KPI))
                    except Exception,e:
                        logger.warn('Exception %s raised, when trying to get the target_KPI string' % (str(e)))
                        target_KPI=None
                    logger.info('calculated target_KPI=%s' % (target_KPI))
                
                if not target_KPI:
                    logger.error('target_KPI property of target_KPIX (X=process number) are not defined !! It is mandatory')
                    raise SyntaxError('target_KPI property of target_KPIX (X=process number) are not defined !! It is mandatory')
                
                # Control that we have a KPI defined for each process 
                NbOfKpi=len(target_KPI.split(','))
                if  NbOfKpi!= cls.numberOfProcess:
                    errMsg='"target_KPI" parameter "%s" MUST contains as many KPI (%d) as number of processes: "%d"' % (target_KPI, NbOfKpi, cls.numberOfProcess)
                    logger.error(errMsg) 
                    raise SyntaxError(errMsg)
                
                # Global scenario TPS (to not be mixed up with individual TPC calls)
                sumKPI=sum(map(float,target_KPI.split(',')))
            
                # relative KPI contribution of the scenario is indexed on the process number
                percent = float(target_KPI.split(',')[cls.processNumber])/sumKPI
            
                # Take care removing spaces at the end if any
                rampup_string_percentage=properties.get('throughput_rampup_percentage').strip() or None
                if not rampup_string_percentage:
                    raise SyntaxError('throughput_use_percentage=True and required parameter "throughput_rampup_percentage" not found !""')     
                
                # transform rampup_string_percentage to global ramp up string
                # No check : 
                rampup_string=' '.join(imap(lambda x: str( float(x.split(',')[0])/100 *sumKPI)+','+x.split(',')[1] , rampup_string_percentage.split()))
                                
                logger.info('[process=%d] [rampup_string="%s"]' % (grinder.processNumber, rampup_string))
                
                # we have to apply the percentage to each element of the rampup string
                try:
                    throughput_profile=' '.join(imap(lambda x: str((float(x.split(',')[0])*percent)/agents)+','+x.split(',')[1] , rampup_string.split()))
                    print '\n'+'-'*80
                    print '>>> [process=%02d] [percent=%6.2f] [throughput_profile=%s]' % (cls.processNumber, percent, throughput_profile)
                    print '='*80+'\n'
                    if logger.isDebugEnabled():
                        logger.debug('[process=%d] throughput_profile=%s' % (cls.processNumber, throughput_profile))
                except:
                    logger.error('rampup_string "%s" - error when applying percent "%f"' % (rampup_string, percent))
            else:            
                throughput_profile=properties.get('throughput_rampup%d' % (cls.processNumber))

            if not throughput_profile:
                raise SyntaxError('"OneFileByProcess" set and "NumberOfProcess" > 0 and "throughput_activate" set but "throughput_rampup%d" property not defined!' % (cls.processNumber))
                
            #
            # Several possibilities for throughput_target
            # - defined explicitly per process
            # - or globally and spread per percentage
            #
            throughput_target=properties.getInt('throughput_target%d' % (cls.processNumber),-1)
            if not throughput_target:
                throughput_target=properties.getInt('throughput_target',-1)
                if throughput_target>0:
                    throughput_target=round(throughput_target*percent)
            
            # A worker may be in throughput mode  
            for scenario  in cls.scenarioList.getList(): #if one of the scenario is asynchronous, we add the graceful period
                if scenario.isAsynchronous():
                    throughput_profile = '%s 0.0001,%d' % (throughput_profile.strip(), cls.scenarioList.getAsyncTimeout())
                    logger.info('Adding a graceful period for Worker %d, [throughput_profile=%s]' % (cls.processNumber, throughput_profile))
                    break
                throughput_profile = throughput_profile.strip()
                
        else:
            #
            # One process only
            #
            throughput_target=properties.getInt('throughput_target',-1)
            throughput_profile=properties.get('throughput_rampup')
            if not throughput_profile:
                raise SyntaxError('"OneFileByProcess" set and "throughput_activate" set but "throughput_rampup" property not defined!')
            if cls.async:
                throughput_profile = '%s 0.0001,%d' % (throughput_profile.strip(), cls.scenarioList.getAsyncTimeout() )
                logger.info('Adding a graceful period , [throughput_profile=%s]' % ( throughput_profile))
            throughput_profile = throughput_profile.strip()        
    
        logger.info( ">>>>> Switching to throughput mode ... [throughput_method=%s][Rampup profile=%s][numberOfThreads=%d][target=%d]" % 
                     (throughput_method, throughput_profile, cls.numberOfThreads, throughput_target))
        # Last parameter is for debugging purpose
        cls.metronom = Metronom( method=throughput_method, profile=throughput_profile, nbThreads=cls.numberOfThreads, 
                                           reporter=cls.clientReporter, target=throughput_target)

    @classmethod
    def __manageClientReporter(cls):
        logger.info('Reporting activation: %s'  % (Configuration.use_reporter))
        if Configuration.use_reporter:
            
            #
            # agentName: grinder.hostID is the standard way to set a naming for a specific agent 
            #            by default, if we have 2 agents, the first one will get hostname-0, the second hostname-1 ... 
            # Warning: sometimes we get the full domain name separated with dot. (so we split and keep the first)
            #
            agentName=properties.get('grinder.hostID') or  socket.gethostname().split('.')[0]
            
            # 
            # report_show_process=True  : you want to have all the per process metrics in the graphing tool
            # report_show_process=False : you have metrics per agent (or hostname)
            # 
            location = '%s.%d' % ( agentName, CoreGrinder.getRealProcessNumber()) if properties.getBoolean('reporter_show_process',False) else agentName
            
            reporter_tool_name = properties.get('reporter_tool')
            reporter_tool = (reporter_tool_name or '').lower() or 'centralreporter'            
            reporter_target={'centralreporter':CentralReporterClient,'carbonreporter':CarbonCacheClient, 'statsd':StatsdClient }
            reporterModule = None
            if reporter_tool not in reporter_target:
                try:
                    reporterModule = __import__('corelibs.stats.%s' % reporter_tool_name, globals(), locals(), ['%s' % reporter_tool_name], -1)
                except (Exception, JavaException), e:
                    logger.error('FAILED invalid property reporter_tool [corelibs.stats.%s], failed with reason: [%s]' % (reporter_tool_name, e))
                    if isinstance(e, JavaException):
                        raise Exception(e)
                    raise
            
            reporterHost = properties.get('reporter_host') or 'localhost'
            reporterPort = properties.getInt('reporter_port', 1901)
            
            # all the ordered testnames of all the scenarios
            testnames= [line.testName for scenario in cls.scenarioList.getList() for line in scenario.lines ] 
            
            if reporter_tool == 'centralreporter':
                # remove duplicates from the testname list
                testnames=list(set(testnames))
                try:
                    cls.clientReporter = CentralReporterClient(reporterHost, reporterPort, location, testnames)
                except:
                    logger.error('[reporter=%s][host=%s][port=%d][location=%s][testnames=%s]' % (reporter_tool,reporterHost,reporterPort,location, testnames))
            elif reporter_tool == 'statsd':
                try:
                    # reporter_aggregate_value aimed at grouping values (the machine location is absent)
                    # test names are indexed by the the process number index (process0=test0, ... )
                    location = '' if properties.getBoolean('reporter_aggregate_value', False) else '%s' % location
                    
                    cls.clientReporter = StatsdClient(reporterHost, reporterPort, location)
                except Exception,e:
                    logger.error('statsd reporter - Exception=%s\n[reporter=%s][host=%s][port=%d][location=%s]' % (str(e),reporter_tool,reporterHost,reporterPort,location))
                    raise RuntimeError('Exception=%s\nUnable to start the statsd reporter ([reporter=%s][host=%s][port=%d][location=%s])' % (str(e),reporter_tool,reporterHost,reporterPort,location) )
            elif reporter_tool == 'carbonreporter':
                raise NotImplementedError('Must be tested !!!')
            elif reporterModule:
                try:
                    cls.clientReporter = getattr(reporterModule, reporter_tool_name)(reporterHost, reporterPort, location)
                except (Exception, JavaException), e:
                    logger.error('FAILED instantiating reporter_tool [corelibs.stats.%s], failed with reason: [%s]' % (reporter_tool_name, e))
                    if isinstance(e, JavaException):
                        raise Exception(e)
                    raise
            
            
            # Initiatial value for TPS
            cls.clientReporter.setTPS(0)
                        
            logger.info( 'Connecting to "%s" on "%s" (%d) for scenario "%s"' % (reporter_tool, reporterHost, reporterPort, location))

    @classmethod
    def __launchRegulator(cls):
        #------ Busy management
        regulator_target=properties.get('regulator_target',None)
        logger.info( 'Regulator activated - initial TPS=%d' % (cls.initialTPS))
        regulator_debug =properties.getBoolean('regulator_debug', False)
        if regulator_debug:
            initialTPS=properties.getInt('regulatorInitialTPS', 1)
        Configuration.metronom = Metronom( method='FLAT', profile=initialTPS, nbThreads=cls.numberOfThreads, reporter=cls.clientReporter,
                                           target=regulator_target)
        Configuration.monitor=Monitor(  initialTPS ,properties, regulator_debug)
                    

    @classmethod
    def getClientReporter(cls):
        return cls.clientReporter

    @classmethod
    def getMonitor(cls):
        return cls.monitor

    @classmethod
    def getMetronom(cls):
        return cls.metronom

    @classmethod
    def getrouterContextClient(cls):
        return cls.routerContextClient
        
    @classmethod
    def getSmscDriver(cls):
        return cls.smscDriver
    
    @classmethod
    def isAsync(cls):
        return cls.async
    
    @classmethod
    def isThroughputActivated(cls):
        return cls.use_throughput

    @classmethod
    def isWaitingMode(cls):
        return cls.waiting_mode
    
    @classmethod
    def setAsync(cls):
        cls.async=True
        
    @classmethod
    def sessionIncrement(cls):
        cls.clientReporter.incrementSessions()
        
    @classmethod
    def sessionDecrement(cls):
        cls.clientReporter.decrementSessions()
