'''
Created on 23 sept. 2014

@author: omerlin
'''

#----------------------------------------------------------------------
from __future__ import with_statement
import time
from threading import Condition

from org.slf4j import MDC

from corelibs.asynclog import asynclog
from corelibs.configuration import Configuration
from corelibs.context import Context
from corelibs.contextCallback import HTTPServerCallback
from corelibs.contextIdentifier import ContextIdentifier
from corelibs.contextLock import ContextLock
from corelibs.coreGrinder import CoreGrinder
from corelibs.grinderQueue import GrinderQueue
from corelibs.reporting import reporting
from corelibs.token import AbortRunToken


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


class asynchronous:
    '''
        static classes aimed at grouping asynchronous logic of grindertool  
    '''
    mutex=Condition()
     
    @classmethod
    def manage_exception(cls, __ctx):
        '''
        Necessary to cleanup the run stack when an error happens on an async step 
        :param context: current context when error was raised
        :param indexLine: the index of the async line where error happened
        '''
        logger.trace('<<ASYNC>> manage_exception() - Adding AbortRunToken to cancel promised async run')
        
        # Other async steps are promised and already counted in the number of runs
        # So we create AbortRunToken to consume them
        [GrinderQueue.put(AbortRunToken()) for line in __ctx.scenario.lines[__ctx.indexLine:] if line.isAsynchronous() and line.asyncBlocking()]
                

    @classmethod
    def call_before(cls,__ctx):


        # ZERO, increase the number of context waiting (should be clean up in case of expiration)
        # *** This Object is useful for Validation mode ***
        # TODO: check this is not useless - as the number of waiting context is in the ContextIdentifier class
        if __ctx.line.asyncBlocking():
            ContextLock.contextIncrease()        
            
            if logger.isTraceEnabled():
                logger.trace('<<ASYNC>> asynchronous.call_before() - contextIncrease() & lock() - [ContextLock=%d]' % (ContextLock.count()))
        
        if not __ctx.line.multipleCaller:
            
            # This is the expiration criteria in ContextIdentifier reaper thread
            #
            __ctx.line.timeout=int(__ctx.line.timeout)
            # expiration date in milli seconds (-1 means NO expiration)
            expirationTime = ( (__ctx.line.timeout + time.time())* 1000 if __ctx.line.timeout != -1 else -1) 
            __ctx.setExpirationTime(expirationTime)
            
            #
            # FIRST, get the context identifier value
            #  3 cases:
            #    value: ${VAR}                        
            #    value: xxxx                     => a fixed literal value
            #    "value" keyword is not defined  => get the current value from the contextKey in the running context
            # 
            
            # Remember: line is only a definition (Immutable)
            contextKeyValue = __ctx.line.contextValue if __ctx.line.contextValue else __ctx.line.contextKey
            __ctx.contextKey=__ctx.line.contextKey
            __ctx.contextValue = __ctx.getCacheKeys().getValue(contextKeyValue) 

            asynclog.logTrace(pos='%s.call_before' % (cls.__name__), msg='Initializing key/value',key=__ctx.contextKey,value=__ctx.contextValue)
            
            if not __ctx.contextValue:
                asynclog.logError(pos='%s.call_before' % (cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue,
                                  msg='\ncache=%s' % (__ctx.getCacheKeys().dictRuntime), err='No value found in cache')
                raise SyntaxError('[Asynchronous step] contextKey "%s" must have a value in the context or have a "value","contextValue" defined in the scenation' % (__ctx.contextKey))
    
            asynclog.log(pos='%s.callBefore' % (cls.__name__), key=__ctx.contextKey,value=contextKeyValue, msg='initial async identifiers')
    
            
            # SECOND, send the JSON message to the ContextManager process
            #---------------------------------------------------------------
            # TODO: manage the case there is no context router !
            # TODO: manage the case we have only SMPP callback
            jsonMessage=None
            if __ctx.line.use_contextManager:
                try:
                    # client call to the router
                    # Time expressed in milliseconds
                    jsonMessage='{"contextKey" : "%s", "value" : "%s", "host" : "%s", "port" : "%s", "expirationtime": "%s", "count": "%d"}' % (__ctx.contextKey,                                                                                                                                    
                                                  __ctx.contextValue,HTTPServerCallback.getHost(),HTTPServerCallback.getPort(), expirationTime,__ctx.line.callbackCount)
                    Configuration.getrouterContextClient().postJsonMessage(jsonMessage, Configuration.getrouterContextClient().getCreateUri() )
                    logger.debug('CREATE - Posting the callback router [message: %s]' % (jsonMessage))
                except Exception, e:
                    logger.error('CREATE - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
                    raise Exception('CREATE - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
        
            # bet that the call will succeed - so we store the contextKey, value doubleton in ContextIdentifier cache
            # We bet the oneWay will succeed, so we store the context for the callback
            asynclog.logInfo(pos='%s.callBefore' % (cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, msg='Storing a cloned context')

            with cls.mutex:
                cloneContext= Context(__ctx.macrosAllScenario)
                cloneContext.copy(__ctx)
                asynclog.logTrace(pos='%s.callBefore' % cls.__name__, key=__ctx.contextKey,value=__ctx.contextValue,
                                  msg='Cloned object address: %s, original address=%s, context=%s' % (hex(id(cloneContext)), hex(id(__ctx)), cloneContext))
                
                try:
                    ContextIdentifier.add_ctx(__ctx.contextKey, __ctx.contextValue, cloneContext)        
                except Exception, e:
                    raise(e)
            
            return jsonMessage

        jsonMessage=None
        if __ctx.line.use_contextManager:

            # Ok this is the special case of multiple message
            msg=[]
            for k,v in __ctx.contextKey.iteritems():
                v= __ctx.getCacheKeys().getValue(  v if v else k)  
                
                # expiration date in milli seconds
                expirationTime = (__ctx.line.timeout[k] + time.time())* 1000 

                msg.append( '{"contextKey" : "%s", "value" : "%s", "host" : "%s", "port" : "%s", "expirationtime": "%s", "count": "%d"}' % (k,                                                                                                                                    
                                                      v,HTTPServerCallback.getHost(),HTTPServerCallback.getPort(), expirationTime,__ctx.line.callbackCount))
            jsonMessage='[' + ','.join(msg) + ']'
                
            try:
                Configuration.getrouterContextClient().postJsonMessage(jsonMessage, Configuration.getrouterContextClient().getCreateBatchUri() )
                logger.debug('CREATE BATCH - Posting the callback router [message: %s]' % (jsonMessage))
            except Exception, e:
                logger.error('CREATE BATCH - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
                raise Exception('CREATE BATCH - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
        
        #
        # Store all the waiting context
        #
        for k,v in __ctx.line.contextKey.iteritems():
            v= __ctx.getCacheKeys().getValue(  v if v else k)  
            with cls.mutex:
                cloneContext= Context(__ctx.macrosAllScenario)
                cloneContext.copy(__ctx)
                cloneContext.setExpirationTime( (__ctx.line.timeout[k] + time.time())* 1000)
    
                try:
                    logger.trace('[%s.call_before][key="%s"][value="%s"] batching - adding into contextIdentifier' % (cls.__name__, k, v) )
                    ContextIdentifier.add_ctx(k,v, cloneContext)        
                except Exception, e:
                    logger.error('[%s.call_before][key=%s][value=%s] - batching - ContextIdentifier.add() failed - cause: %s' % (cls.__name__,__ctx.contextKey, __ctx.contextValue, str(e)))
        
        return jsonMessage
    
    
  
    @classmethod
    def call_after(cls, __ctx, response, jsonMsg):

        if 'errorCode' not in response:
            logger.error('%s.call_after - "errorCode" was not found in your response, this is required in your implementation !' % (cls.__name__))
            raise SyntaxError('%s.call_after - "errorCode" was not found in your response, this is required in your implementation !' % (cls.__name__))
        
        errorCode=int(response['errorCode'])    

        # Optimistic lock bet failed : we correct this
        if  errorCode not in  (200,0):
            ContextIdentifier.pop_ctx(__ctx)
        
        # context manager is for protocols like http (not for smpp)
        if __ctx.line.use_contextManager:
            # Case we were too optimistic and we have got an error during the synchronous HTTP call
            if  errorCode not in  (200,0): #TODO decorelate totally errorCode & http.status
                try:
                    Configuration.getrouterContextClient().postJsonMessage(jsonMsg,Configuration.getrouterContextClient().getDeleteUri() )
                    logger.info('DELETE - Posting the callback router [message: %s]' % (jsonMsg))
                except Exception, e:
                    logger.error('DELETE - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
                    raise Exception('DELETE - Error posting message to the contextRouter, stacktrace=%s' % (str(e)))
                finally:
                    # We stop the current scenario
                    asynchronous.manage_exception(__ctx)
                    # Mark error code
                    response['errorCode']=-1
                return
    
    
    @classmethod
    def manage_async_break(cls, __ctx):
        
        # No break by default
        ret=False
                
        # ASYNCHRONOUS - BREAK ALL - release the current thread execution
        if __ctx.line.isAsynchronous() and __ctx.line.asyncBlocking():

            with cls.mutex:
                # the standard async flow is cancelled ?
                if ContextIdentifier.isFlagged(__ctx.contextKey,__ctx.contextValue):
                    asynclog.log(pos='%s.manage_async_break' %(cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, 
                                 msg=' We keep the thread, the notification callback is passed ...', ctx=__ctx)
                    
                    # update context cache with callback cache
                    ContextIdentifier.updateCache(__ctx)
                    
                    # cleanup in this case, as we move to next step
                    ContextIdentifier.pop_ctx(__ctx)
                    
                    # Decrease all asynchronous counters & print value if trace level 
                    ContextLock.decreaseAllCounters('<<ASYNC>> %s.manage_async_break()' % (cls.__name__))                                 
                    
                    # the processing will continue in the same thread
                    ret= False
                else:
                    # release lock
                    ContextIdentifier.unlock(__ctx.contextKey,__ctx.contextValue)
                    
                    asynclog.log(pos='%s.manage_async_break' %(cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, 
                                       msg='UNLOCK DONE - releasing the thread ...')            
                    
                    # Normal async process is confirmed
                    ret=True
            
        return ret
            

    @classmethod
    def process_callback(cls, __ctx, __data):
        
        __key,__value=__ctx.contextKey,__ctx.contextValue

        # Decrease all asynchronous counters & print value if trace level 
        ContextLock.decreaseAllCounters('<<ASYNC>> %s.process_callback()' % (cls.__name__))
        
        # For debugging purpose, uid maintains an unique identifier in the log files
        MDC.put('uid','[uid=%s]' % (__ctx.uid))

        # Ask to the implementation to process asynchronous data returned
        asynclog.log(pos='%s.process_callback' % cls.__name__, key=__key, value=__value,
                     msg='resuming with notification data : %s'% (__data))

        #
        # if the step as a tag async with a property timeout_success: True
        # coming back to the callback method means there was no timeout
        # so this is an assertion failure
        #
        if __ctx.line.isTimeoutSuccess():
            reporting.report_step_status(success=False, context=__ctx, cause='Assertion Failure: a timeout was expected', 
                                         state='AsyncStepAssertTimeoutSuccessKO', synchronous=False)
            __ctx.endAsyncScenario()
            return True
                
        try:
            # Load an alternative implementation defined in the callback_implementation tag
            if __ctx.line.callback_implementation:
                asynclog.log(pos='%s.process_callback' % cls.__name__, key=__key, value=__value,
                             msg='post-processing notification data with implementation "%s"'% (str(__ctx.line.callback_implementation)))
                class_implementation=__ctx.scenario.loaded_implementations[str(__ctx.line.callback_implementation)]
                processedData =class_implementation.process_data(__data)
            else:
                # Calling back the implementation to interpret the Mock data
                processedData = __ctx.getCurrentLine().getImplementation().process_data(__data)
        
        except (SyntaxError,KeyError), x:
            asynclog.logError(pos='%s.process_callback' % cls.__name__, key=__key, value=__value,
                              msg='SyntaxError/KeyError raised when processing process_data()', err=str(x))
            logger.error('[state=StopAsyncStepFatalError][cause=%s][test=%s][scenario=%s]' % (repr(x), __ctx.line.getTestName(), __ctx.scenario))
            reporting.report_step_status(success=False, synchronous=False, context=__ctx, 
                                         cause="%s\n while processing test '%s' in scenario '%s'" % (x, __ctx.line.getTestName(), __ctx.scenario), state='StopSAsynctepFatalError')
            raise SyntaxError("%s\n while processing test '%s' in scenario '%s'" % (x, __ctx.line.getTestName(), __ctx.scenario))
                               
        # could be raised by process_data()
        except Exception, cause:
            asynclog.logError(pos='%s.process_callback' % cls.__name__, key=__key,value=__value,
                              msg='SyntaxError/KeyError raised when processing process_data()',err=str(x))
            # last boolean parameter means : caused by an async callback 
            reporting.report_step_status(success=False, synchronous=False, context=__ctx, cause=cause, state='stopAsyncStepKO')
            __ctx.endAsyncScenario()
            return True
       
        # interpreted mock data must be a dictionary
        if not isinstance(processedData, dict):
            asynclog.logError(pos='%s.process_callback' % cls.__name__, key=__key,value=__value,
                              msg='The asynchronous processed data must be a dictionary, [data:%s] [type:%s]' % (processedData, type(processedData)), err=str(x))
            raise SyntaxError('The asynchronous processed data must be a dictionary, [data:%s] [type:%s]' % (processedData, type(processedData)))
        
        # Adding the processed data - Before assertion !!
        asynclog.log(pos='%s.process_callback' % cls.__name__, key=__key, value=__value,
                     msg='Adding the context added data : %s'% processedData)
        __ctx.cacheKeys.update_cache_temporary(processedData)                    
        
        # ok, if we have a response in the data structure, we can apply assertion on it
        assertionFailed, cause = __ctx.getCurrentLine().checkResponse(processedData, __ctx, True)
        if 'deviceId' in __ctx:
            cause='[deviceId=%s]%s' % (__ctx['deviceId'], cause)

        if assertionFailed:
            reporting.report_step_status(success=False, synchronous=False, context=__ctx, cause=cause, state='AsyncStepAssertKO')
            __ctx.endAsyncScenario()
            return True
                
        asynclog.log(pos='%s.process_callback' % cls.__name__, key=__key,value=__value,
                     msg='[After async assertion] we cache permanently processed data')
        # processed data are now part of the cache for the current run 
        __ctx.cacheKeys.update_asyncData_permanently(processedData)                    

        return False

