"""
Created on 23 sept. 2014

@author: omerlin
"""

from net.grinder.script import InvalidContextException
from net.grinder.script.Grinder import grinder

from corelibs import toolbox
from corelibs.collector_proxy import proxy
from corelibs.configuration import Configuration
from corelibs.coreGrinder  import CoreGrinder

properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()

loggerProxy=proxy.getLoggerProxy()


class reporting:
    """
       More an utility class for better code structure (readability)
    """

    @classmethod
    def localization(cls, __ctx):
        return '[test=%s][async=%s][step=%d][testid=%d][scenario=%s][scenarioId=%d]' % (__ctx.line.getTestName(),
                                                                                                  __ctx.line.isAsynchronous(),
                                                                                                  __ctx.indexLine, 
                                                                             __ctx.line.getTestId(), __ctx.scenario.getName(),                                                                              
                                                                              __ctx.indexScenario )
                                                                                           
    @classmethod
    def sendData_fatal(cls, __ctx,  error_context, response):
        
        cause= "%s\n while processing test '%s' in scenario '%s'" % (error_context, __ctx.line.getTestName(), __ctx.scenario)
                         
        # Validation reporting
        reporting.report_step_status(success=False, synchronous=True, context=__ctx, cause=cause, state='StopStepFatalError',
                                     response=response)      
    
    @classmethod
    def sendData_failure(cls, __ctx,  cause, response):
        
        # Validation reporting
        reporting.report_step_status(success=False, synchronous=True, context=__ctx, cause=cause, state='StopStepKO',
                                    response=response)      
    
    @classmethod
    def sendData_success(cls, __ctx, response):
        state='AsyncStopStepOK' if __ctx.line.isAsynchronous() else 'StopStepOK'
        reporting.report_step_status(success=True, synchronous=True, context=__ctx, cause='normal completion'
                                     , state=state, response=response)

    @classmethod
    def report_step_status(cls, **kargs):
        
        success=kargs['success']
        __ctx=kargs['context']
        cause=kargs['cause']
        state=kargs['state']
        synchronous=kargs.get('synchronous', True)
        
        # Validation reporting
        response=kargs.get('response', None)
        if response and Configuration.outTraceActivated:
            reporting.outputTraceForValidation(__ctx, response)

        status='success'
        
        if Configuration.use_reporter:
            Configuration.getClientReporter().addNbCallCount(__ctx.line.getTestName())

        if success:
            logger.info('[state=%s][status=%s][cause=%s]%s' % (state, status, cause, cls.localization(__ctx)))
            if synchronous:
                logger.trace('grinder.statistics.forLastTest.success = 1')
                grinder.statistics.forLastTest.success = 1
                grinder.getStatistics().report()
                
        else:
            status='failed'
            logger.error('[state=%s][status=%s][cause=%s]%s' % (state, status, cause, cls.localization(__ctx)))
            if Configuration.use_reporter:
                Configuration.getClientReporter().addNbCallErrorCount(__ctx.line.getTestName())

            if synchronous:
                try:
                    logger.trace('grinder.statistics.forLastTest.success = 0')
                    grinder.statistics.forLastTest.success = 0
                    grinder.getStatistics().report()
                except InvalidContextException, x:
                    logger.info('raise an InvalidContextException, meaning we are not in a post-processing of a grinder Test, reason: %s' % (x))

        # LogProxy feature
        result_id = loggerProxy.log_result(status, stepname=__ctx.line.getTestName() or 'none', state=status,
                                           why=cause, scenario=__ctx.scenario.input_file or 'none')
        if result_id:
            logger.info("[loggerProxy.log_result] ~~~~~ RESULT ID: %s ~~~~~" % result_id)
            
    @classmethod            
    def outputTraceForValidation(cls, __ctx, response):
        """
        For Validation :
               Write logs to a specific file if properties "fileout" & "outTraceActivated" are set
        Remark: Kept for compatibility (originally from AOTA mtas code)
        :param __ctx: Test execution context
        :param response: response dictionary got from implementation
        """
        if isinstance(response, dict):
            try:
                # log the required output line (removed 3 output string (%s) columns)
                buildStr = '%s|%d|%s|%s|%s|%s|%s' % (__ctx.scenario.input_file,
                                                     __ctx.indexLine,
                                                     __ctx.line.getTestName(),
                                                     response.get('httpStatCode', '500'),
                                                     str(response.get('errorCode', '-1')),
                                                     response.get('responseText', 'Error raised - no details'),
                                                     __ctx.line.getLastTemplate())
                toolbox.concurrentFileWrite(Configuration.fOut, buildStr, Configuration.cv_out)
        
            except Exception, x:
                raise SyntaxError('FATAL: Error writing string to output file, cause: "%s"'% x)
        
          
        #
        # there are three levels of EXTRA logging: none, some, and all
        #    none means that there is no additional logging done, so only one output file
        #
        #    the next logging levels create an additional logging file
        #        each of these two levels includes the line read from the input file
        #    error means to only log errors, and so the error response will be included
        #    all means to log all responses
        #
        if Configuration.outTraceActivated:
            if Configuration.extraLevel == 'all' or (response.get('errorCode',-1) not in (200,204) and Configuration.extraLevel == 'error'):
                toolbox.concurrentFileWrite(Configuration.fOutExtra, 
                                            '%s|%d|%s' % (__ctx.scenario, __ctx.indexLine, response.get('responseText', 'Error raised - no details')),
                                            Configuration.cv_ext)