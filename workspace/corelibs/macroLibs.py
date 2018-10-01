'''
Created on 24 sept. 2014

@author: omerlin
'''
import copy
from java.util.regex import Pattern
import socket
from threading import Condition
import types

from corelibs.coreGrinder import CoreGrinder, MockGrinder
from corelibs.filetoolbox import ExtendedTemplate, load_module


#import macros
#------------------------------------------
#------------------------------------------
#------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()
#------------------------------------------


def get_hostID():
    return properties.get('grinder.hostID') or  socket.gethostname().split('.')[0]

def get_agentId( hostID):
    '''
      Extract any number from a simple string to get a unique agent identifier from the grinder.hostID
      return the string if not found (generally the hostname)
    :param hostID: the grinder.hostID string
    '''
    m=Pattern.compile('([0-9]+)').matcher(hostID)
    if m.find():
        return m.group(1)
    return hostID
    
def loadProps():
    d=dict(properties)
    # For testing purpose
    if isinstance(grinder,MockGrinder):
        d.update({
                'grinder.threads':1,
                'grinder.runNumber':0,
                'grinder.threadNumber':0,
                'grinder.processNumber':0, 
                'AGENT':0,
                'RUN':0,
                'THREAD':0,
                'PROCESS': 0 })   
        return d
    
    if grinder:
        d.update({
                'grinder.hostID': get_hostID(),
                'grinder.runNumber':grinder.getRunNumber(),
                'grinder.threadNumber':grinder.getThreadNumber(),
                'grinder.processNumber':CoreGrinder.getRealProcessNumber(), 
                'grinder.agentNumber': '%02d' % (grinder.getAgentNumber()),
                'HOST':socket.gethostname().split('.')[0],
                'HOSTID': get_hostID(),
                'AGENTID': get_agentId(get_hostID()),
                'AGENT': '%02d' % (grinder.getAgentNumber()),
                'RUN':grinder.getRunNumber(),
                'THREAD':grinder.getThreadNumber(),
                'PROCESS': CoreGrinder.getRealProcessNumber() })
    return d

PATTERN_WITH_NAME=r'\s*(\w+)\s*=\s*(\w+)\.(\w+)\((.*)\)$'
PATTERN_WITHOUT_NAME=r'[#]{0,1}[!]{0,1}(\w+)\.(\w+)\((.*)\)$'


class CachedMacros:
    
    macro_pattern = Pattern.compile(PATTERN_WITHOUT_NAME)
    macro_pattern_with_name = Pattern.compile(PATTERN_WITH_NAME)

    loadedMacros={}
    macros=[]
    cv=Condition()
    
    
    def __init__(self, scenarioId=None, macroList=None):
        '''
          Load all the macros we have in a list for each scenario
        :param scenarioId: the scenario identifier
        :param macroList: a list of macros to initialize
        '''
        if macroList:
            [self.__class__.__load_macro(scenarioId, MacroStr) for MacroStr in macroList]
    
    
    def update(self,scenarioId, macroList=None):
        self.__init__(scenarioId, macroList)
        
    
    @classmethod
    def getMacrosList(cls):
        return cls.macros

    @classmethod
    def getInitialMacrosInstances(cls):
        return cls.loadedMacros
  
    def copyMacros(self):
        '''
           To correct performance issue with getMacroInstance()
        '''
        loadedMacrosCopy=dict()
        for k in self.__class__.loadedMacros:
            loadedMacrosCopy[k]={}
            for x in self.__class__.loadedMacros[k]:
                try:
                    loadedMacrosCopy[k][x]=copy.deepcopy(self.__class__.loadedMacros[k][x])
                except:
                    raise
        return loadedMacrosCopy
    
    
    @classmethod
    def getMacrosInstances(cls):
        '''
          python copy.deepcopy is not thread safe. So we protect with a lock
          may change in jython 2.7 (see http://sourceforge.net/p/jython/mailman/message/32911285/ )
        '''
        cls.cv.acquire()
        loadedMacrosCopy=copy.deepcopy(cls.loadedMacros)
        cls.cv.release()
        
        return loadedMacrosCopy

    @staticmethod
    def __manageDefaultValue( s, d ):
        '''
           Add default value to templating
           For example:
             ${grindertool.msisdn.min},${grindertool.msisdn.max},${grinder.threads},${grindertool.msisdn.padding,5},${grindertool.msisdn.random,1},${grindertool.msisdn.debug,1}
             ${grindertool.msisdn.padding,5} is replaced by 5 if key grindertool.msisdn.padding is not defined.
             (...)
        :param s: the macros argument list with potential default template values
        :param d: the dictionary where the template key are defined
        '''
        regexp=Pattern.compile('(\$\{([a-zA-Z0-9\.]+),([a-zA-Z0-9\.]+)}?)')
        m = regexp.matcher(s)
        while m.find():
            rep=str(d.get(m.group(2),m.group(3)))
            s=s.replace(m.group(1),rep)
        return s

    @staticmethod
    def __load_macro_instance(MacroModule, MacroFactoryFunction, args=None):
        '''
             Dynamically call a factory function of a python module
             The factory function should return an instance of a local class of this module.
             
        :param MacroModule: python module from the macro library
        :param MacroFactoryFunction: function we want to call to get the macro object
        :param args: String arguments passed to the MacroFactoryFunction 
        '''
        instance=None
        # the arguments of the MacroFactoryFunction can be a grinder placeholder
        if args:
            # New: default value management
            props=loadProps()
            args=CachedMacros.__manageDefaultValue(args, props)
            
            # First try, ignore any substitution error (safe_substitute does the job)
            args=ExtendedTemplate(args).safe_substitute(props)
            
            # Still a template variable ?
            if args.find('${')>=0:
                try:
                    # Any not substituted key raise an error (paranoid mode)
                    args=ExtendedTemplate(args).substitute(props)
                except KeyError, e:
                    logger.error('__load_macro_instance() - KeyError raise, reason: %s' % str(e))
                    raise SyntaxError('__load_macro_instance() - KeyError raise, reason: %s' % str(e))
                

        # Revalidate that our macro library knows our module
        try: 
            myModule = load_module( MacroModule, 'macros')
        except:
            raise SyntaxError('Your macros dont contain "%s". Are you sure your macro directory is up to date?' %
                              (MacroModule))
                
                
        logger.info('modules: "%s' % (dir(myModule)))
        
        # Load the macro
        #myMacro = getattr(myModule, MacroModule)
                
        # instantiate the function - it should return an object instance    
        try:
            return getattr(myModule, MacroFactoryFunction)(args) if args else getattr(myModule, MacroFactoryFunction)()
        except Exception, x:
            logger.trace("stack trace = %s \n mymodule: '''%s''' search '%s' '%s' args: '%s' "%
                         (x, myModule, MacroFactoryFunction, types.ModuleType, args))

            raise SyntaxError("Error running the Macro object Factory function: %s.%s('%s'):\n '''%s'''" %
                              (myModule,MacroFactoryFunction,args or '<empty parameter from scenario>', x))
        
    
    @classmethod
    def __load_macro(cls, scenarioId, MacroFunction):
        '''
           Create an instance of a class object - this will be loaded and cached in a hash
           macros must have an initializer that return an instance of the class.
           New - OME, 15/5/14 - add the possibility to have several named instance of a class object
           :param MacroFunction: the function name to execute
        '''
        if scenarioId not in cls.loadedMacros:
            cls.loadedMacros[scenarioId]={}
        
        logger.info('Evaluating macro: "%s"' % (MacroFunction))    
        # Macros **without** names
        m1 = cls.macro_pattern.matcher(MacroFunction)
        if m1.matches():
            cls.macros.append(MacroFunction)            
            (module,methodName,args) = (m1.group(1), m1.group(2), m1.group(3))
            if module not in cls.loadedMacros[scenarioId]:
                logger.debug('[Macro=%s] - Loading instance of [module=%s],[methodName=%s],[args=%s]' %
                             (MacroFunction, module,methodName,args))
                cls.loadedMacros[scenarioId][module] = cls.__load_macro_instance(module, methodName, args)
                return
        
        # macros **with** name 
        m2 = cls.macro_pattern_with_name.matcher(MacroFunction)
        if m2.matches():
            cls.macros.append(MacroFunction)
            (instanceName, module,methodName,args) = (m2.group(1), m2.group(2), m2.group(3),m2.group(4))
            if not cls.loadedMacros[scenarioId].has_key(instanceName):
                cls.loadedMacros[scenarioId][instanceName] = cls.__load_macro_instance(module, methodName, args)
                logger.debug('[Macro to evaluate: %s] [Macro=%s] - Loaded instance name of [module=%s],[methodName=%s],[args=%s]' %
                             (MacroFunction, instanceName, module,methodName,args))
                return
        else:
            logger.error('Macro "%s" did not match the regular expression "%s"\n Check you do not forget the instantiation method' % (MacroFunction, PATTERN_WITH_NAME))
            raise SyntaxError('Macro "%s" did not match the regular expression "%s"\n Check you do not forget the instantiation method' % (MacroFunction, PATTERN_WITH_NAME))

class ExecMacros:

    fooPattern = Pattern.compile(r'&{0,1}([a-zA-Z]{1}[_a-zA-Z0-9]+)\.(\w+)\((.*)\)')
    simpleFooPattern = Pattern.compile(r'&{0,1}([a-zA-Z]{1}[_a-zA-Z0-9]+)\.(\w+)\(([^\)]*)\)')
    placeholderPattern = Pattern.compile(r'\$\{([\w\.]+)\}')
    
    # A list of dictionary. Each list index is a scenario
    macros=CachedMacros.getInitialMacrosInstances()
    
    # =======================
    # PRIVATE    
    # =======================
    @classmethod
    def __isMacroInside(cls, macroStr, pattern):
        m = pattern.matcher(macroStr)
        if m.find():
            return (True, m.group(1), m.group(2), m.group(3))
        return (False, None, None,None)  

    @classmethod
    def __maySubstituteTemplate(cls, param, templateDict):
        if (cls.placeholderPattern.matcher(param)).find():
            try:
                return (  ExtendedTemplate(param).substitute(templateDict) )
            except KeyError:
                raise SyntaxError('Unable to find "%s" in the context' % (param))
        return param
    
    @classmethod
    def __execMethod(cls, module, method, param=None, templateDict=None):
        
        # Templating substitution if any
        paramList=[]
        if param:
            for k in param.split(','):
                paramList.append(  cls.__maySubstituteTemplate( k , templateDict) )
            if logger.isTraceEnabled():
                logger.trace('[param="%s"][templateDict="%s"]\n\t[list="%s"]' % (param, templateDict,paramList))
      
        
        if module not in cls.macros:
            raise SyntaxError('module "%s" was not loaded ! check the "macros" section in your scenario')

        # setattr() to set context inside the macro
        #==========================================
        try:
            logger.debug('__execMethod(): setAttr(), type: %s' % (type(cls.macros[module])))
            setattr(cls.macros[module],'ctx',templateDict)
            
        except Exception, e:
            raise Exception('Failure when setting "ctx" to macro "%s", reason: %s' % (module, e))
        
        try:
            
            return getattr(cls.macros[module],method)(*paramList) if paramList else getattr(cls.macros[module],method)()
        except Exception, e:
            raise Exception('__execMethod(): Failure when calling macro "%s.%s(%s)", reason: %s' % (module, method, param, e))
            
    @classmethod
    def setMacrosIndex(cls, index):
        '''
           The macros instance are stored as a list of dictionary
           Each index of the list is a scenario.
           Each scenario has a dictionary of macros.
        :param index: scenario index
        '''
        cls.macros=CachedMacros.getInitialMacrosInstances()[index]
    
    @classmethod
    def callMacro(cls, macroStr, templateDict):
        '''
           A macro is a string with a "module.method( parameter )" format
           Calling a macro means executing a method call with template substitution
           Template uses the python String.Template class substitution
           The dictionary for substitution is passed as a parameter.
           Method call may contains sub macro calls.
           Only one sub level of macro call is currently supported              
        :param macroStr: the macro to execute
        :param templateDict: the template dictionary for substitution
        '''
        # Check if we have a function call
        # Remark: the regexp pattern take the FULL parameter so we may have several sub function call
        (found, module1 , method1, param1) = cls.__isMacroInside(macroStr, cls.fooPattern)
        # Case 1: No macro => we replace potential template
        if not found:
            return cls.__maySubstituteTemplate(macroStr, templateDict);
        
        if param1:            
            while(1):
                # Check if there is a sub function call
                # Remark: the regexp pattern take ONLY the macro parameter
                (found2,module2 , method2, param2) = cls.__isMacroInside(param1, cls.simpleFooPattern)
                if not found2:
                    break;
                param1 = param1.replace('%s.%s(%s)' % (module2,method2,param2), str(cls.__execMethod(module2, method2, param2, templateDict)))
            
        return cls.__execMethod(module1, method1, param1, templateDict) 

    @classmethod
    def eval(cls, macroString, ctx, literal_usage):
        try:
            subsStr = macroString
            if logger.isTraceEnabled():
                logger.trace ('[eval] rule "%s" [literalUsage=%s]' % (macroString, literal_usage))  
            if not literal_usage:
                subsStr =  ExtendedTemplate(macroString).substitute(ctx) 
                if logger.isTraceEnabled():
                   logger.trace ('[eval] rule after substitution "%s" [literalUsage=%s]' % (subsStr, literal_usage))  
            try:
                return eval( subsStr)
            except Exception, e:
                raise SyntaxError('[eval] Boolean evaluation on "%s" failed, reason: %s' % (subsStr, e))
        except KeyError:
            raise SyntaxError('[eval] One template was not substituted in "%s" with context "%s"' % (subsStr, ctx))




