'''
Created on 30 juil. 2014

@author: omerlin
'''
# grinder dependencies
import copy

from net.grinder.script.Grinder import grinder
from org.slf4j import MDC

from corelibs.collector_proxy import proxy
from corelibs.configuration import Configuration
from corelibs.coreGrinder  import CoreGrinder
from corelibs.filetoolbox import ExtendedTemplate, GlobalPattern
from corelibs.grinderQueue import GrinderQueue
from corelibs.reporting import reporting
from corelibs.token import AbortRunToken


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

# For custom logging
loggerProxy=proxy.getLoggerProxy()


class CacheKey:
    '''
      At each run, for each step execution, with have key/value data to substitute 
      - (level 1) global parameters (CoreGrinder.getProperties() )
      - (level 1) Grinder execution context 
      - (level 2) context values (for a thread run) - in the context section of a Yaml scenario
      - (level 2) step (line) execution values 
      - (level 2) memorization values between steps and template
      - (level 2) token coming for asynchronous callback with their key/value context
      IMPORTANT : the reset() property loose level 2 key/values between 2 runs
    '''
    def __init__(self):
        self.dictRuntime={}
        self.dictWithContext={}
        # From asynchronous OR waiting mode tokens
        self.dictDynamicContext={}
        self.reset() 
            
    def getPaddedRunNumber(self):
        return str(grinder.runNumber).zfill(int(properties.getProperty('runNumberPadding') or 5))
    def getPaddedThreadNumber(self):
        return str(grinder.threadNumber).zfill(int(properties.getProperty('threadNumberPadding') or 4))
    def getPaddedProcessNumber(self):
        return str(grinder.getProcessNumber() - grinder.getFirstProcessNumber()).zfill(int(properties.getProperty('processNumberPadding') or 2))
    def getPaddedAgentNumber(self):
        return str(grinder.getAgentNumber()).zfill(int(properties.getProperty('agentNumberPadding') or 2))
        
    def reset(self):
        if grinder:
            self.dictRuntime=dict(properties)
            self.dictRuntime.update({
                    'grinder.agentNumber':grinder.getAgentNumber(),
                    'grinder.runNumber':grinder.getRunNumber(),
                     'grinder.threadNumber':grinder.getThreadNumber(),
                     'grinder.processNumber':grinder.getProcessNumber() - grinder.getFirstProcessNumber(), 
                    'AGENT':grinder.getAgentNumber(),
                    'RUN':grinder.getRunNumber(),
                     'THREAD':grinder.getThreadNumber(),
                     'PROCESS': grinder.getProcessNumber() - grinder.getFirstProcessNumber(), 
                     'grinder.runNumber.padded' : self.getPaddedRunNumber(), 
                     'grinder.threadNumber.padded' : self.getPaddedThreadNumber(), 
                     'grinder.processNumber.padded' : self.getPaddedProcessNumber(),
                     'grinder.agentNumber.padded' : self.getPaddedAgentNumber()})
            self.dictRuntime.update(self.dictDynamicContext)
            self.dictDynamicContext={}
    
    def get(self):
        return self.dictRuntime
    
    def set(self, key,value):
        self.dictRuntime[key]=value
        
    def getValue(self, key):
        return self.dictRuntime.get(key,None)
 
    def update_keys(self, keys):
        self.dictRuntime.update(keys)


    def update_keys_not_conflicting(self, keys):
        for k,v in keys.iteritems():
            if k not in self.dictRuntime:
                self.dictRuntime[k]=v
    
    def add_dynamic_keys(self, keys):
        logger.trace('add_dynamic_keys() : %s' % (keys))
        self.dictDynamicContext.update(keys)
 
    def update_cache_temporary(self, keys):
        '''
          For async flows, add async processed  data temporary
          
        :param keys: async data dict
        '''
        logger.trace('update_dynamic_keys() : %s' % (keys))
        self.dictRuntime.update(keys)


    def update_keys_permanently(self, keys):
        '''
           We want to keep the keys in the cache for next steps
           :param keys: the keys (memorization for instance)
        '''
        # For next steps (so permanently)
        self.dictWithContext.update(keys)
        # But also if we are using it immediately in the same step (temporary)
        self.dictRuntime.update(keys)


    def update_asyncData_permanently(self, data):
        '''
          For async flows, store async data permanently
        :param keys: async data dict
        '''
        if logger.isTraceEnabled():
            logger.trace('<<CACHE>> %s.update_asyncData_permanently, data: %s' % (self.__class__.__name__, data) )
        self.dictWithContext.update(data)

        
    def setContextMarker(self):
        '''
           Save permanent values between each step
           Called at the end of a new scenario context update (  getNextScenario().updateContextCache()  )
        '''
        self.dictWithContext=dict(self.dictRuntime)
         
    def resetToContextMarker(self): 
        '''
           At each step, reset cache to persistent data
        '''
        if logger.isTraceEnabled():
            logger.trace('<<CACHE>> %s.resetToContextMarker, data: %s' % (self.__class__.__name__, self.dictWithContext) )
        self.dictRuntime=dict(self.dictWithContext)

class Context:
    '''
       A context maintains the :
       - Yaml context execution value between RUN
       - all the cached values during a scenario lifecycle
       
       Remark:
          keys are ** unknown ** - they are pushed in the context environment and reused in the scenario
          ** coherence of keys ** are the sole responsibility of the tester
    '''

    def __init__(self, macrosAllScenario):

        # =========== IMMUTABLE attributes =================
        # we reverse because we will use a pop() to traverse the scenario
        self.scenarioList=Configuration.getScenarioList()
        self.scenarioListSize=len(self.scenarioList)
        self.macrosAllScenario=macrosAllScenario
        #
        self.templateManager= Configuration.cmdMgr
        
        # =========== MUTABLE attributes =================
        self.uid=None
        self.macros=None
        # expiration time = infinite by default
        self.expirationTime=-1
        self.indexScenario=-1
        self.scenario=None
        self.line=None
        self.indexLine=-1
        self.scenarioSize=0
        
        # For async hardening
        self.locked=False
        self.flagged=False
        self.contextKey=None
        self.contextValue=None
        
        # A flag to indicates that the scenario must be continued on resume 
        # Bug in Rev373 - the default value was True
        self.scenarioContinue=False
                        
        # The initial context is the "meta" definition of the context 
        self.__initial_context=None
        
        # This is the living context with substitution
        self.stored=None

        # A thread context cache 
        self.cacheKeys = CacheKey()
                
       
    def copy(self, __ctx):
        '''
           ATTENTION: must copy all the mutable attributes (see above) 
           :param __ctx: the context object to copy
        '''
        self.uid=__ctx.uid
        self.macros=__ctx.macros
        self.expirationTime=__ctx.expirationTime
        self.indexScenario=__ctx.indexScenario
        self.scenario=__ctx.scenario
        # take care ... Line must be immutable !
        self.line=__ctx.line
        self.indexLine=__ctx.indexLine
        self.scenarioSize=__ctx.scenarioSize
        # 
        self.contextKey=__ctx.contextKey
        self.contextValue=__ctx.contextValue
        
        self.scenarioContinue=__ctx.scenarioContinue
                        
        # The initial context is the "meta" definition of the context 
        self.__initial_context=__ctx.__initial_context
        
        # This is the living context with substitution
        self.stored=__ctx.stored

        # A thread context cache 
        self.cacheKeys = copy.deepcopy(__ctx.cacheKeys)
    
    
    '''
       #### BEGIN - applicative locks used for asynchronous processing
    '''
    def unlock(self):
        self.locked=False
    def setLock(self):
        self.locked=True
    def isLocked(self):
        return self.locked
    def setFlag(self):
        self.flagged=True
    def isFlagged(self):
        return self.flagged
    
    '''
       #### END - applicative locks used for asynchronous processing
    '''
    
       
    def __repr__(self):
        s=''
        s+='\n<%s.%s object at %s>\n' % (self.__class__.__module__,self.__class__.__name__,hex(id(self)))
        s+='scenario: %s\n' % (hex(id(self.scenario)) if self.scenario else 'None' )         
        s+='line(%d): %s\n' % (self.indexLine,hex(id(self.line)) if self.line else 'None' )  
        s+='scenarioList(%d): %s\n' % (self.indexScenario, hex(id(self.scenarioList)) if self.scenarioList else 'None')       
        return s 
 
    def getIndexScenario(self):
        return self.indexScenario
    
    def getNextScenario(self):
        '''
          Switch to the next scenario. 
          Localization is done by scenario and indexScenario attributes
          TODO: check if self.stored is still used ...
        '''
        self.indexScenario+=1
        self.macros=None
        
        # Check we don't reach the last scenario
        if self.indexScenario>=self.scenarioListSize:
            logger.debug('getNextScenario() - End Of Scenario - indexScenario=%s, Number of scenario=%d' % (self.indexScenario, self.scenarioListSize))
            self.scenario=None
            self.indexScenario=-1
            return
        
        # An Unique Identifier aimed at giving an identification of the UC  
        self.uid = '%01d%02d%03d%05d%03d' % (grinder.agentNumber,Configuration.processNumber,grinder.threadNumber,grinder.runNumber,self.indexScenario)
        MDC.put('uid','[uid=%s]' % (self.uid))
        
        # Manage current scenario variables
        self.scenario=self.scenarioList[self.indexScenario]
        self.scenarioSize=len(self.scenario.lines)
        if self.macrosAllScenario:
            if self.indexScenario in self.macrosAllScenario:
                self.macros=self.macrosAllScenario[self.indexScenario]
        
        # get immutable information from scenario object
        self.__initial_context=self.scenario.getContextDefinition()
        logger.debug('getNextScenario() - [scenario:%s] [initialContext:%s] ' % (self.scenario, self.__initial_context))
        self.stored=dict(self.__initial_context)
        self.indexLine=-1
        
        # Update the Context cache for the new scenario
        self.cacheKeys.reset()
        
        # add the unique identifier for implementation relying on a static session cache
        self.cacheKeys.set('grindertool.transactionId', self.uid)        
        
        # Add all the context evaluated keys
        if len(self.__initial_context)>0:
            if logger.isTraceEnabled():
                logger.trace('-- Begin context evaluation [context="%s"][size=%d]' % (self, len(self.__initial_context)))
            
            # Evaluate macros in context
            temp_dict=dict(self.__initial_context)
                       
            # TODO : recursive
            nbRetryLoop=4
            for i in range(1,nbRetryLoop):
                needSubstitutionCount = 0 
                for k,v in dict(temp_dict).iteritems():
                    if logger.isTraceEnabled():           
                        logger.trace('[loop=%d][key=%s][value=%s]' % (i,k,v) )
                    v =  ExtendedTemplate(v).safe_substitute(self.cacheKeys.get())         
                    (stillPlaceholder, newValue ) = self.__substitute_in_value( v)
                    if logger.isTraceEnabled():
                        logger.trace('.........[key=%s][value=%s][stillPlaceholder=%s][returnValue=%s]' % (k,v,stillPlaceholder, newValue) )
                    needSubstitutionCount += int(stillPlaceholder)  
                    temp_dict[k]=newValue
                    if not stillPlaceholder and newValue:
                        if type(newValue) is dict:
                            for key,val in newValue.iteritems():
                                if logger.isTraceEnabled():
                                    logger.trace('Adding key "%s.%s" value %s to scenario context' % (k,key,val))
                                self.cacheKeys.set('%s.%s' % (k,key),val)
                        else:
                            self.cacheKeys.set(k,newValue)
                        
                        if logger.isTraceEnabled():
                            logger.trace('Removing key from temporary context: %s' % (k) )
                        temp_dict.pop(k)
                if not needSubstitutionCount:
                    if logger.isTraceEnabled():
                        logger.trace('No more substitution needed [Exit at loop %d/%d]' % (i,nbRetryLoop))
                    break 
                
        # We define the context cache keys
        self.cacheKeys.setContextMarker()
        if logger.isTraceEnabled():
            logger.trace('-- End context evaluation --')
    
    
    def getScenario(self, asyncCallback=False):
        return  self.scenario if asyncCallback else self.getNextScenario()

    def setExpirationTime(self, expirationTime):
        '''
        Expiration is set when executing at runtime an async step
        :param expirationTime: a future date in second for expiration including the timeout initialized in Line class
        '''
        self.expirationTime = expirationTime    
    
    def getCacheKeys(self):
        return self.cacheKeys
 
    
    def getNextLine(self):
        '''
          go to the scenario next line (step) of it exists
        '''
        self.indexLine+=1
        if self.indexLine>=self.scenarioSize:
            # VIRTUALRUN END #
            self.indexLine= -1
            self.line=None
            return False
        
        self.line=self.scenario.lines[self.indexLine]
        
        # To avoid side effect
        if self.line.async_step:
            self.line.contextValue=self.line.initialContextValue
            if logger.isTraceEnabled():
                logger.trace('[ASYNC] restoring initialContextValue definition: %s' % (self.line.contextValue))
        return True
        
    def getCurrentLines(self):
        return self.scenario.lines
    
    def getCurrentLineIndex(self):
        return self.indexLine
    
    def getCurrentLine(self):
        return self.line

    def endAsyncScenarioTimeout(self):
        '''
           Case where we consider a timeout as a normal behavior
           timeout_success: True in the "async" tag
           default ( timeout_success: False )
        '''
        # Special case : timeout EXPIRED is a success
        if self.line.isTimeoutSuccess():
            logger.trace('endAsyncScenarioTimeout - considering a timeout as a SUCCESS')
            self.scenarioContinue=True
            GrinderQueue.put(self)
            return
    
        #
        # Nominal UC: timeout is a failure. 
        # ome,29/02: removed the last parameter of report_step_status to raise the flag error in the grindertool GUI
        # ome, 10/07/17: removing last parameter was not a good idea as it raise a "InvalidContextException"
        #
        reporting.report_step_status(success=False, context=self, cause='Timeout error triggered', state='stepTimeoutKO', synchronous=False)
#         reporting.report_step_status(success=False, context=self, cause='Timeout error triggered', state='stepTimeoutKO')
        self.endAsyncScenario()

    def endAsyncScenario(self):
                  
        # There is another scenario behind, we increase the scenario index and put it in the queue
        if self.indexScenario < (self.scenarioListSize-1):
            logger.debug('endAsyncScenario: case indexScenario[%d] < number of scenario minus one[%d]' % (self.indexScenario,self.scenarioListSize-1))
            # We take care to remove any promised async call of the stopped scenario
            for i,line in enumerate(self.scenario.lines[self.indexLine:]):
                # ignore the current expired one 
                if i==0 and line.isAsynchronous(): continue
                if line.isAsynchronous() and line.asyncBlocking():
                    logger.trace('endAsyncScenario: adding extra AbortRunToken for scenario[%d]:%s' % (self.indexScenario, self.scenario.getName()))
                    GrinderQueue.put(AbortRunToken()) 
            logger.trace('endAsyncScenario: adding context in the GrinderQueue()' )
            GrinderQueue.put(self)
            return
    
        # There is no more scenario
        logger.trace('endAsyncScenario: Last scenario - Adding AbortRuntoken when removing context')
        loggerProxy.end_run('end run')
        [GrinderQueue.put(AbortRunToken()) for line in self.scenario.lines[self.indexLine:] if line.isAsynchronous() and line.asyncBlocking()]

    def processNew(self):
        '''           
           Process a ***template**** line with dynamic substitutions and memorization
        '''        
        # To be sure that we won't have some side effect with fields and memory cache        
        self.cacheKeys.resetToContextMarker()
        
        if logger.isTraceEnabled():
            logger.trace('>>> processNew(): cachekeys: %s' % (self.cacheKeys.dictRuntime))

        #=======================
        # Necessary to have a thread local copy of immutable line object
        #==========================
        localFields=copy.deepcopy(self.line.fieldsNew)

        # Update the cacheKeys with <<<literal values>>> (values without function and without template ${template} )
        subsDict={}
        for elem in localFields.getLiterral():
            subsDict[elem.name]=elem.value
            logger.trace('********** literal field:%s' % (elem))
        self.cacheKeys.update_keys(subsDict)
            
        # Then substitute all <<<template strings>>> found in the fields to allow function execution        
        for elem in localFields.getTemplate():
            elem.setValue( ExtendedTemplate(elem.value).safe_substitute(self.cacheKeys.get()) )
                
        # Dynamic function call in the field itself is marked for the whole line (optimization)
        if localFields.isFunction:
            logger.debug('processLine() - Dynamic fields substitution')
            for elem in localFields.getFunction():
                m = (GlobalPattern.dynFieldPattern).matcher(elem.value)
                while m.find():
                    (module,method,param)= (m.group(1),  m.group(2),  m.group(3) or None)
                    if logger.isTraceEnabled():
                        logger.trace('%s[module=%s][method=%s][param=%s]' % (elem,module,method,param))
                    try:
                        valueToReplace = getattr(self.macros[module],method)(param) if param else getattr(self.macros[module],method)()
                        if logger.isDebugEnabled():
                            logger.debug('valueToReplace=%s' % (valueToReplace))
                        if not valueToReplace:
                            logger.error('valueToReplace is null. REVIEW YOUR TEST DEFINITION. Context is [module=%s][method=%s][param=%s]' % (module,method,param))
                            raise SyntaxError('valueToReplace is null. REVIEW YOUR TEST DEFINITION. Context is [module=%s][method=%s][param=%s]' % (module,method,param))
                    except KeyError:
                        logger.error('FATAL: Macro call "%s.%s(%s)" is not defined in your scenario "%s" macros section' % (module, method, param, self.scenario.getName() ))
                        raise SyntaxError ('FATAL: Macro call "%s.%s(%s)" is not defined in your scenario "%s" macros section' % (module, method, param, self.scenario.getName()))
                    except Exception, x:
                        if not self.macros:
                            logger.error('FATAL: your forget to define the macros section in your scenario "%s"' % (self.scenario.getName()))
                            raise SyntaxError ('FATAL: your forget to define the macros section in your scenario "%s"' % (self.scenario.getName()))
                        else:
                            logger.error('FATAL: when calling macro: %s, cause=%s' % (elem,x)) 
                            raise SyntaxError('FATAL: when calling macro: %s, cause=%s' % (elem,x)) 

                    elem.setValue(m.replaceFirst(valueToReplace))
                    m = (GlobalPattern.dynFieldPattern).matcher(elem.value)

        # Add all the line fields in the cacheKey cache
        subsDict={}
        for elem in localFields.getAllFields():
            subsDict[elem.name]=elem.value
        self.cacheKeys.update_keys(subsDict)
        
        str2Use=None
        if self.line.template:
            # template could be dynamic (depending on context)
            template=self.line.getDynamicTemplate(self.cacheKeys.get(), self.macros) if self.line.dynTemplate else self.line.template
            
            # return the cached template (or store it the first time)
            command=self.templateManager.get_or_load(self.line.template_type, template, self.macros)
            
            # the common case is to have Yaml format
            if command.getStr():
                str2Use = ExtendedTemplate(command.getStr()).safe_substitute(self.cacheKeys.get())
                logger.debug('[Yaml Template after substitution:%s]' % (str2Use))    
                return str2Use
        
        # No template, return just the fields with substitution applied                
        str2Use = localFields.update(self.cacheKeys.get())
        logger.debug('[NoTemplate] str2Use=%s' % (str2Use))
                
        return  str2Use

    
    def __stillPlaceHolder(self, param):
        '''
          Do we have a placeholder in the param string ?
        '''
        return (GlobalPattern.dynPlaceholderPattern).matcher(param).find()

    def __macroInside(self, value):
        module = method = param = None
        m = (GlobalPattern.dynFieldPattern).matcher(value)
        found=m.find()
        if found:
            (module , method, param) = (m.group(1), m.group(2), m.group(3))
            logger.debug('context - __macroInside(%s): %s' % (value, '%s.%s(%s)' % (module,method,param or '')))
            # Checking that macro exists
            if not self.macros:
                raise SyntaxError('You are using a macro, defined by "%s" but no macros where initialized in the "macros" tag' % (value))
            if not module in self.macros: 
                raise SyntaxError("FATAL(context.__macroInside): failed to locate instance for Macro '%s' while evaluating %s.%s('%s')! [Macros=%s]" %
                                  (module, module, method, param or '<empty parameter from scenario>',str(self.macros)) )
        return (found, module, method, param or None)
    
    def __substitute_in_value(self, value):
        '''
          Does the value has a macro or placeholder to substitute ?
        '''
        stillPlaceholder=False
        returnValue=value
        (found, module1 , method1, param1) = self.__macroInside(value)
        if found:
            logger.trace('[value=%s][isMacro=%s][module1=%s][method1=%s][param1=%s]' % (value,found, module1 , method1, param1) )
            if param1:
                (found2, module2 , method2, param2) = self.__macroInside(param1)
                # a sub macro is found
                if found2:
                    stillPlaceholder = self.__stillPlaceHolder( param2 )
                    if not stillPlaceholder:
                        toReplace='%s.%s(%s)' % (module2,method2,param2)
                        ret = getattr(self.macros[module2],method2)(param2) if param2 else getattr(self.macros[module2],method2)()
                        returnValue = value.replace(toReplace, str(ret))
                        logger.trace('Inner macro call : [value=%s][toReplace=%s][ret=%s][returnValue=%s]' % (value, toReplace, ret, returnValue))
                        stillPlaceholder = self.__stillPlaceHolder( returnValue)  
                else:
                    stillPlaceholder = self.__stillPlaceHolder( param1 )
                    if not stillPlaceholder:
                        returnValue = getattr(self.macros[module1],method1)(param1) 
            else:
                stillPlaceholder=False
                toReplace='%s.%s(%s)' % (module1,method1,param1 or '')
                ret=getattr(self.macros[module1],method1)()
                returnValue = value.replace(toReplace,str(ret))   
                logger.trace('[returnValue=%s][value=%s][toReplace=%s][call=%s]' % (returnValue, value, toReplace, ret))                           
        else:
            returnValue = value
            stillPlaceholder = self.__stillPlaceHolder(returnValue)
            
        return (stillPlaceholder, returnValue)

        
    def update(self, k, v):
        self.stored[k] = v      
    
    def get_keys(self):
        return self.stored.iteritems()
    
    def get_key(self, key):
        return self.stored.get(key,None)
    def get(self, key):
        return self.stored.get(key,None)
    def set(self, key, value):
        self.stored[key]=value
   
    def reset_context(self):
        '''
           Reset context to its original "metadata" context
        '''
        self.stored=dict(self.__initial_context)
        logger.debug('====> reset_context: [initial:%s] [stored=%s]' % (self.__initial_context,self.stored))
         
   
