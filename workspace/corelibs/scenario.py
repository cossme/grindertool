'''
Created on 31 juil. 2014

@author: omerlin
'''

from __future__ import with_statement
# regular python libraries
from threading import Condition
from java.io import StringReader
from java.lang import Exception as JavaException
from java.lang import Thread
from java.util import LinkedHashMap, ArrayList
from java.util.regex import Pattern
from javax.xml.parsers import DocumentBuilderFactory
from javax.xml.xpath import XPathFactory, XPathConstants
from org.xml.sax import InputSource
import os
import sys
import traceback
from org.yaml.snakeyaml import Yaml, DumperOptions
from org.yaml.snakeyaml.constructor import Constructor
from org.yaml.snakeyaml.error import MarkedYAMLException, YAMLException
from org.yaml.snakeyaml.parser import ParserException
from org.yaml.snakeyaml.reader import ReaderException
from org.yaml.snakeyaml.representer import Representer
from org.yaml.snakeyaml.scanner import ScannerException

from corelibs.BaseConfiguration import BaseConfiguration
from corelibs.Fields import InputField
from corelibs.macroLibs import CachedMacros, ExecMacros
from corelibs.coreGrinder import CoreGrinder, MySyntaxError
from corelibs.filetoolbox import ExtendedTemplate, GlobalPattern, load_protocol
from corelibs.memory import MemoryField
from corelibs.yaml_custom import CustomResolver
from corelibs.checkRule import CheckRule
# JSON 
from org.skyscreamer.jsonassert import JSONAssert
from java.lang import AssertionError as JavaAssertionError

# ----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()


# ----------------------------------------------------------------------

def flatten_dict(d):
    '''
       convert a python complex object construct from a Yaml to a simple generator of flatened items
       See test_flatten.py for details.
       THIS NOT CALLED directly but thru the to_flattened_dictionary() function
        
       :param d: a dictionary for the first call, then on recursive calls (dict,list,ArrayList, LinkedHashMap) 
    '''
    if isinstance(d, (dict, LinkedHashMap)):
        for k, v in (d if isinstance(d, dict) else dict(d)).items():
            if isinstance(v, (dict, list, ArrayList, LinkedHashMap)):
                for item in flatten_dict(v):
                    yield '%s.%s' % (k, item)
            else:
                yield '%s.%s' % (k, v)
    if isinstance(d, (list, ArrayList)):
        for i, v in enumerate(d if isinstance(d, list) else list(d)):
            if isinstance(v, (dict, list, ArrayList, LinkedHashMap)):
                for item in flatten_dict(v):
                    yield '%d.%s' % (i, item)
            else:
                yield '%d.%s' % (i, v)


def to_flattened_dictionary(d):
    '''
      
      for each complex element convert to flattened one.
      Let others unchanged.
      
    :param d: a dictionary coming from Yaml loading
    '''
    # filter to see if we have complex structure
    d1=dict((k, v) for k, v in d.iteritems() if isinstance(v, (ArrayList, LinkedHashMap)))

    # No complex element, stop it
    if not d1:
        logger.trace('No update on dictionary "%s"' % (d))
        return d

    logger.trace('Kept only COMPLEX element in dictionary: "%s"' % (d1))

    # So d1 is not null, filter only str element
    d2=dict((k, v) for k, v in d.iteritems() if isinstance(v, (str, unicode)))

    logger.trace('Kept only STRING element in dictionary: "%s"' % (d2))

    # Flatten d1 complex structure
    # flatten_dict is a generator that returns tuple. We have to join with '.' separator. 
    # Last element in tuple is the value. All others elements joined are the key.
    #
    d3=dict(('.'.join(k.split('.')[:-1], ), k.split('.')[-1]) for k in list(flatten_dict(d1)))
    logger.trace('Result of complex element flattening: "%s"' % (d3))

    # d2 + d3 = what we want
    d2.update(d3)
    # Warning Take care to not return d2.update(d3) as this is an in place update that return None
    return d2


class Teardown(object):
    def __init__(self, macro):
        self.macro=macro
        if not GlobalPattern.dynFieldPattern.matcher(self.macro).find():
            raise SyntaxError('The macro "%s" format is incorrect, macro format is "module.function(parameter)"' % self.ruleDefinition['macro'])
        logger.trace('teardown "macro" to evaluate: %s' % self.macro)


class Line:
    # to protect
    mutex=Condition()
    testCounter=0

    def __init__(self, **kargs):
        """
            init Line with dictionary structure
        """
        # the scenario context part 
        context=kargs['context']

        self.yaml_format=kargs['yaml_format']
        # To be sure to have separated range of test in the Grinder console
        self.testName=kargs.get('testname', None)
        if not self.testName:
            raise MySyntaxError(
                '[Yaml syntax] a name is required for a step ! PLS add a key "name" for your step definition')

        # The grinder Test() test identifier (used in grindertool.py)
        self.__class__.testCounter+=1
        self.testId=self.__class__.testCounter
        if BaseConfiguration.oneFileByProcess:
            self.testId=CoreGrinder.getRealProcessNumber() * BaseConfiguration.testRangeSize + self.__class__.testCounter

        self.stopOnError=kargs.get('stopOnError', False)

        # protocol and protocol class implementation 
        self.implementation=kargs['implementation']
        self.protocol=kargs['protocol']
        last_protocol=kargs['last_protocol']

        # Assertion rules on the line validation and storage as CheckRule objects
        self.assertion=False
        self.checkRules=[]
        if kargs['assertion']:
            self.assertion=True
            # Create a rule per element (dict) of the list
            for i, k in enumerate(kargs['assertion']):
                logger.debug('Declaring rule %d: [%s]' % (i, str(k)))
                self.checkRules.append(CheckRule(k))

        # Teardown macros and logger
        self.teardown=False
        self.teardownOperation = []
        if kargs['teardown']:
            self.teardown=True
            for i, k in enumerate(kargs['teardown']):
                logger.debug('Declaring Teardown objects %d: [%s]' % (i, str(k)))
                self.teardownOperation.append(Teardown(k))

        # Sleep definition on step
        # Default, declared in second (so a scale factor of 1000)
        self.step_sleep_scale=1000
        self.step_sleep=kargs.get('sleep')
        self.step_sleep_defined=self.step_sleep is not None
        if self.step_sleep_defined:
            if ('after' not in self.step_sleep) and ('before' not in self.step_sleep):
                raise MySyntaxError('Yaml sleep not well defined - missing one of key "before","after"')
            if 'unit' in self.step_sleep:
                if self.step_sleep['unit'].upper().startswith('MILLI'):
                    self.step_sleep_scale=1
            if 'before' in self.step_sleep:
                self.step_sleep['before']=float(ExtendedTemplate(self.step_sleep['before']).safe_substitute(context))
            if 'after' in self.step_sleep:
                self.step_sleep['after']=float(ExtendedTemplate(self.step_sleep['after']).safe_substitute(context))

        # [VRZ] sleep breaking for lag management between POD 
        if properties.getBoolean('protocol_lag_management', False):
            if last_protocol and last_protocol != self.protocol:
                if '%s_lag_sleep' % self.protocol in properties:
                    if not self.step_sleep_defined:
                        self.step_sleep_defined=True
                    self.step_sleep['before']=properties.getDouble('%s_lag_sleep' % self.protocol)

        # is this step asynchronous or not ?
        self.async_step=kargs.get('async')
        # By default, the step is using context manager
        if self.async_step:
            self.use_contextManager=True
            logger.debug('Asynchronous keys definition: %s' % (self.async_step.keys()))

            # check format
            if not set(('contextKey', 'timeout')).issubset(self.async_step.keys()):
                logger.error('contextKey, timeout required keys are not defined for asynchronous call')
                raise MySyntaxError('contextKey, timeout required keys are not defined for asynchronous call')

            # Special case of multiple async call & blocking=False
            self.multipleCaller=self.async_step.get('multipleCaller', False)

            # if multiple async calls, they are dictionaries
            self.contextKey=self.async_step['contextKey']
            self.timeout=self.async_step['timeout']

            # Keys expected when checking callback
            self.requiredKeys=self.async_step.get('requiredKeys')

            # New feature - The number of callback to wait for before continuing next step
            self.callbackCount=int(self.async_step.get('callbackCount', 1))

            # (Validation) Consider a timeout on an async call as a success
            self.timeoutSuccess=self.async_step.get('timeout_success', False)

            # blocking=False is a special feature aimed at blocking later
            self.blocking=self.async_step.get('blocking', True)

            # if defined, the key identifier is this value and not the context value of the contextKey variable
            self.contextValue=None
            if 'value' in self.async_step or 'contextValue' in self.async_step:
                self.contextValue=self.async_step.get('value') or self.async_step.get('contextValue')
                if self.contextValue:
                    m=GlobalPattern.dynPlaceholderPattern.matcher(self.contextValue)
                    if m.find():
                        self.contextValue=m.group(1)
                        logger.trace('[ASYNC] init line.contextValue=%s' % self.contextValue)
            self.initialContextValue=self.contextValue

            # If we have assertion here
            if 'assert' in self.async_step:
                if isinstance(self.async_step['assert'], ArrayList):
                    # Create a rule per element (dict) of the list 
                    for i, k in enumerate(list(self.async_step['assert'])):
                        logger.debug('Declaring async rule %d: [%s]' % (i, str(k)))
                        self.checkRules.append(CheckRule(k, True))
                else:
                    logger.error('(async) assert element must contains a list of assertion ( "-" in Yaml)')
                    raise MySyntaxError('(async) assert element must contains a list of assertion ( "-" in Yaml)')

            # knowing the protocol could avoid using the context Manager for http async calls
            self.callback_implementation=None
            if 'callback_protocol' in self.async_step:
                if self.async_step['callback_protocol'].lower() in ('smpp', 'smsc', 'internal'):
                    self.use_contextManager=False
                else:
                    self.callback_implementation=self.async_step['callback_protocol']

        # Template integration        
        self.template=kargs['template']
        self.template_type='without'
        self.lastTemplate=''
        self.dynTemplate=False
        if self.template:
            self.template_type='yaml_inline'
            if isinstance(self.template, (str, unicode)):
                self.template_type=kargs.get('template_type', 'file')
                self.dynTemplate=(GlobalPattern.templateDynamicPattern).matcher(self.template).find()

        self.memoryInInputFile=False
        self.functionFieldSubstitution=False
        self.dynSubstitution=False

        #
        # Input fields management
        #
        self.fieldsNew=None
        if self.yaml_format:
            self.fieldsNew=InputField(kargs['fields'])
            self.functionFieldSubstitution=self.fieldsNew.isFunction

        #
        # Command memorization in variable
        #
        self.memorizeCommand=False
        self.memorizedValues=[]
        if kargs['memory']:
            for k, attributes in kargs['memory'].iteritems():
                if isinstance(attributes, LinkedHashMap):
                    self.memorizedValues.append(MemoryField(k, dict(attributes)))
                else:
                    self.memorizedValues.append(MemoryField(k, attributes))
            self.memorizeCommand=True

        # For Xpath
        self.docBuilder=None
        self.docBuilderFactory=DocumentBuilderFactory.newInstance()

        # Print out the created line object   
        logger.trace('%s' % self)

    def __str__(self):
        """ Return a string representation of Line object.
        """
        s="Line (%s) object representation is : \n" % (hex(id(self)))
        s+=" . implementation: [%20s] . template type:[%10s] template  : [%20s]\n" % (
        self.implementation, self.template_type, self.template)
        s+=" . testname: [%20s] . testId: [%05d] [async=%s]\n" % (self.testName, self.testId, str(self.async_step))
        for memory in self.memorizedValues:
            s+=" . memory  : [%s]\n" % memory
        if self.lastTemplate:
            s+=" . last template : [%s]\n" % self.lastTemplate
        s+=" . fields : %s\n" % self.fieldsNew
        return s

    def do_step_sleep(self, keyword):
        '''
          the possibility to sleep before/after a step execution
          :param keyword: 'after' or 'before' keys
        '''
        if self.step_sleep_defined and keyword in self.step_sleep:
            Thread.sleep(long(float(self.step_sleep[keyword]) * self.step_sleep_scale))
            if logger.isDebugEnabled():
                logger.debug('Sleeping %s during %s %s' % (
                keyword, self.step_sleep[keyword], 's' if self.step_sleep_scale == 1000 else 'ms'))

    def getContextKey(self):
        return self.contextKey

    def getContextValue(self):
        return self.contextValue

    def isTimeoutSuccess(self):
        return self.timeoutSuccess

    def isAsynchronous(self):
        return True if self.async_step else False

    def asyncBlocking(self):
        return self.blocking

    def isAssertionDefined(self):
        return self.assertion

    def checkResponse(self, respDict, ctx, deferred=False):
        '''
              check the response
        :param respDict: the response is part of a dictionary of string
        :param ctx: used only for validation when an assertion rule is not compiled and contains template variable to set
        :param deferred: deferred assertion is for async mode
        '''
        if logger.isDebugEnabled():
            logger.debug('[test=%s] Checking the response' % ctx.line.getTestName())
            logger.trace('>>>> respDict:\n%s' % respDict)

        # Keys in the context.
        ctxKeys=ctx.getCacheKeys().get()

        # Adding the Response keys also in the response evaluation context
        ctxKeys.update(respDict)

        # rules are deferred (asynchronous) or immediate (deferred==False)
        for i, rule in enumerate((rule for rule in self.checkRules if rule.deferred == deferred)):

            logger.debug('Checking rule %d: %s' % (i, rule))

            if rule.ruleType == 'maxduration':
                if ctxKeys['grindertool.step.executionTime'] <= rule.maxDuration:
                    continue
                return True, 'assert failed, step executionTime [%d] is greater than max duration [%d]' % (
                ctxKeys['grindertool.step.executionTime'], rule.maxDuration)

            # ============================
            if rule.ruleType == 'macro':
                ExecMacros.setMacrosIndex(ctx.getIndexScenario())
                # evaluate the macro
                try:
                    if ExecMacros.callMacro(rule.ruleDefinition['macro'], ctxKeys):
                        continue
                    return True, 'assert failed for macro "%s" ' % (rule.ruleDefinition['macro'])
                except Exception, e:
                    return True, 'FAILED "macro" assertion "%s", reason: %s' % (rule.ruleDefinition['macro'], str(e))

            if rule.ruleType == 'eval':
                # eval assumption is to have local variable names identified, so we set "ctx" as a standard variable
                try:
                    if ExecMacros.eval(rule.ruleDefinition['eval'], ctxKeys, rule.literal_usage):
                        continue
                    return True, 'assert failed for eval "%s" ' % (rule.ruleDefinition['eval'])
                except NameError, e:
                    return True, 'FAILED "eval" assertion "%s", reason: %s' % (rule.ruleDefinition['eval'], str(e))
                except Exception, e:
                    return True, 'FAILED "eval" assertion "%s", reason: %s' % (rule.ruleDefinition['eval'], str(e))

            # ============================
            # get the comparison string
            # ============================
            source=None
            sourceFound=False
            if isinstance(respDict, dict):
                # if we have a template, it doesn't include the context keys
                if rule.responseKey in respDict:
                    source=respDict[rule.responseKey]
                    sourceFound=True
                    logger.trace('---> (respDict) rule.responseKey: %s, source: %s' % (rule.responseKey, source))
                # otherwise, have a check in the context keys also
                elif rule.responseKey in ctxKeys:
                    source=ctxKeys[rule.responseKey]
                    sourceFound=True
                    logger.trace('---> (ctxKeys) rule.responseKey: %s, source: %s' % (rule.responseKey, source))

                # Check existence or not of a key in the response (or context )
                if 'exists' in rule.ruleDefinition:
                    _exists_value=str(rule.ruleDefinition['exists']).lower()
                    logger.trace('Evaluating EXIST rule %s' % _exists_value)
                    if _exists_value in ('true', 'yes', 'y'):
                        if source:
                            logger.info('"%s" Exists [match=True]' % rule.responseKey)
                            logger.trace('checkResponse(): response_key "%s" source: "%s" exists' % (rule.responseKey, source))
                            continue
                    elif _exists_value in ('false', 'no', 'n'):
                        if not source:
                            logger.info('"%s" Not Exists [match=True]' % rule.responseKey)
                            logger.trace('checkResponse(): response_key "%s" NOT exists' % rule.responseKey)
                            continue

                    # "exists" rule failed as success means a continue to next rule
                    logger.info('FAILED %s assertion "%s" on key: "%s"' % (rule.ruleType, str(rule.ruleDefinition), rule.responseKey))
                    return True, 'FAILED %s assertion "%s" on key: "%s"' % (rule.ruleType, str(rule.ruleDefinition), rule.responseKey)

                if not sourceFound:
                    logger.info('FAILED %s assertion "%s" key: "%s" does not exist' % (rule.ruleType, str(rule.ruleDefinition), rule.responseKey))
                    return True, 'FAILED %s assertion "%s"key: "%s" does not exist' % (rule.ruleType, str(rule.ruleDefinition), rule.responseKey)

            elif isinstance(respDict, basestring):
                source=respDict
                sourceFound=True
            else:
                raise MySyntaxError('checkResponse() must be applied on a dictionary or a string, we got the type: %s' % (type(respDict)))

            # ================
            # xpath rule 
            # ====================
            if rule.hasXpathRule():
                logger.trace('Evaluating XPATH rule %d' % (i))
                # For validation purpose - not powerful at all - to avoid on performance testing !
                tmp_compiledXpathRule=rule.compiledXpathRule

                with self.__class__.mutex:
                    if not rule.isXpathCompiledRule:
                        tmp_xpathExpression=ExtendedTemplate(rule.xpathExpression).safe_substitute(ctxKeys)
                        logger.trace('rule.xpathExpression=%s' % tmp_xpathExpression)
                        try:
                            xpathFactory=XPathFactory.newInstance()
                            tmp_compiledXpathRule=xpathFactory.newXPath().compile(tmp_xpathExpression)
                        except JavaException, x:
                            exc_type, exc_value, exc_traceback=sys.exc_info()
                            errorMsg=repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                            logger.error('Unable to compile xpath rule "%s", cause: %s' % (tmp_xpathExpression, errorMsg))
                            raise MySyntaxError('Unable to compile  xpath rule "%s", cause: %s' % (tmp_xpathExpression, errorMsg))

                try:
                    #
                    # Error could happen when Gwaf answer with an HTTP error code directly
                    # 
                    xmlIStream=InputSource(StringReader(source))
                    if not self.docBuilder:
                        self.docBuilder=self.docBuilderFactory.newDocumentBuilder()

                    with self.__class__.mutex:
                        doc=self.docBuilder.parse(xmlIStream)

                    nodes=tmp_compiledXpathRule.evaluate(doc, XPathConstants.NODESET)
                    nodes_len=nodes.getLength()
                    if logger.isDebugEnabled():
                        logger.debug('Xpath id=%s, result is %s len is %s' % (hex(id(tmp_compiledXpathRule)), str(nodes), nodes_len))
                        logger.trace('[positiveCheck=%s][ruleType=%s] check %s %s rule on text: "%s"' % (rule.positiveCheck, rule.ruleType, str(rule.ruleDefinition), rule.xpathExpression, source))
                    if nodes_len > 1:
                        if rule.textQuery:
                            logger.info('xpath %s matches more than 1 node, modify the xpath expression' % source)
                            return True, 'xpath %s matches more than 1 node, modify the xpath expression' % source
                        else:
                            # a "TOO_MANY" is also a "NOT_EMPTY", so we adapt depending on the regular expression
                            source='NOT_EMPTY' if rule.regexpExpression == 'NOT_EMPTY' else 'TOO_MANY'
                            sourceFound=True
                    elif nodes_len == 1:
                        # The source for the regexp (contains/notcontains) is the extracted value ...
                        source=str(nodes.item(0).getTextContent()) or ''
                        if not rule.textQuery:
                            source='NOT_EMPTY' if source else 'EMPTY'
                            sourceFound=True
                        logger.debug(
                            '[textQuery=%s][extracted=%s][xpath=%s]' % (rule.textQuery, source, rule.xpathExpression))
                    else:
                        source='NOT_FOUND'
                        sourceFound=True
                        logger.info('nodes element NOT FOUND [rule=%s][xpath=%s]' % (
                        str(rule.ruleDefinition), rule.xpathExpression))

                except JavaException, x:
                    exc_type, exc_value, exc_traceback=sys.exc_info()
                    errorMsg=repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                    logger.error('Error evaluating XML source "%s", reason: %s, details: %s' % (source, x, errorMsg))
                    return True, 'Error evaluating XML source "%s", reason: %s, details: %s' % (source, x, errorMsg)

                    # =========================
            # JSON rule ?
            # ============================
            if rule.jsonRule:
                try:
                    _expected=ExtendedTemplate(rule.regexpExpression).safe_substitute(
                        ctxKeys) if rule.isPlaceholder else rule.regexpExpression
                    logger.trace('JSONassert: comparing %s between "%s" and "%s"' % (
                    'equality' if rule.positiveCheck else 'not equality', source, _expected))
                    if rule.positiveCheck:
                        JSONAssert.assertEquals(_expected, source, rule.jsonStrict)
                    else:
                        JSONAssert.assertNotEquals(_expected, source, rule.jsonStrict)
                except JavaAssertionError, e:
                    logger.info('FAILED JSON assertion "%s" (regexp=%s) on response: "%s"\nreason:%s' % (
                    str(rule.ruleDefinition), _expected, source, str(e)))
                    return True, 'reason="%s", [response="%s"][expected="%s"]' % (str(e), source, _expected)
                except JavaException, x:
                    exc_type, exc_value, exc_traceback=sys.exc_info()
                    errorMsg=repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                    logger.error('Error evaluating JSON "%s", reason: %s, details: %s' % (source, x, errorMsg))
                    return True, 'Error evaluating JSON "%s", reason: %s, details: %s' % (source, x, errorMsg)

                    # Nothing more for JSON path
                return False, None

            # =========================
            # Otherwise Regexp rule
            # ============================
            logger.trace('Evaluating REGEXP rule %d' % (i))
            tmp_compileRule=rule.compiledRule
            # For reporting, to show literal values in static regexp rules
            ruleDefinitionWithoutPlaceholder=str(rule.ruleDefinition)

            try:
                # For validation purpose - not powerful at all - to avoid on performance testing !
                if not rule.isCompiledRule:
                    tmp_regexpExpression=ExtendedTemplate(rule.regexpExpression).safe_substitute(ctxKeys)

                    # Check if we have not special characters (curly braces) Or configured to quote the regexp in the scenario
                    if ('{' in tmp_regexpExpression or '}' in tmp_regexpExpression) or rule.literal_usage:
                        tmp_regexpExpression=Pattern.quote(tmp_regexpExpression)

                    # We use the "equals" parameter in the scenario - so exact matching is asked
                    if rule.equalsRule:
                        tmp_regexpExpression='^%s$' % (tmp_regexpExpression)

                    logger.debug('Not compiled rule - [regexp=%s] - after substitution' % (tmp_regexpExpression))
                    tmp_compileRule=Pattern.compile(tmp_regexpExpression,
                                                    Pattern.CASE_INSENSITIVE | Pattern.DOTALL) if rule.ignoreCase else Pattern.compile(
                        tmp_regexpExpression, Pattern.DOTALL)

                    # replace variable with values in the rule definition (which is a dictionary converted to a string for representation)
                    # This is for debugging purpose (in case of not matching)
                    ruleDefinitionWithoutPlaceholder=ExtendedTemplate(ruleDefinitionWithoutPlaceholder).safe_substitute(
                        ctxKeys)

                source=str(source) if sourceFound else ''
                m=tmp_compileRule.matcher(source)
                match=m.find()
                if logger.isTraceEnabled():
                    logger.trace('Regexp [match=%s] on [source="%s"]' % (str(match), str(source)))
                if not match and rule.positiveCheck or match and not rule.positiveCheck:
                    logger.info('FAILED %s assertion "%s" (regexp=%s) on response: "%s"' % (rule.ruleType,
                                                                                            str(rule.ruleDefinition), rule.regexpExpression, source))
                    return True, '%srule=%s, regexpExpression=%s, literal_usage=%s Evaluation=%s' % (
                                  ruleDefinitionWithoutPlaceholder, rule.regexpExpression, rule.literal_usage, source)
            except JavaException, x:
                exc_type, exc_value, exc_traceback=sys.exc_info()
                errorMsg=repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
                logger.error('Pattern matcher error on source "%s" - cause: "%s"' % (source, errorMsg))
                raise MySyntaxError('Pattern matcher error on source "%s" - cause: "%s"' % (source, errorMsg))

        # Ok, all rules are respected
        return False, None

    def dynFieldsInFile(self):
        return self.dynSubstitution

    def memorizedVariableInputFileEnabled(self):
        return self.memorizedVariableInInputFile

    def getImplementation(self):
        return self.implementation

    def getTestName(self):
        return self.testName

    def setTestId(self, testId):
        self.testId=testId

    def getTestId(self):
        return self.testId

    def getDynamicTemplate(self, keys, macros):
        '''
          Dynamic template for dynamic context processing (advanced usage)
          Template name must have the format: (\w+)&(\w+)\.(\w+)\((.*)\)
          where : 
               group(1)              : a prefix for the template name
               &(\w+)\.(\w+)\((.*)\) : a macro calling of form : module.function( parameters) 
          
          :param keys: the cacheKey dictionary context (see Context & CacheKey classes )
        '''
        self.lastTemplate=self.template
        if self.dynTemplate:
            template=ExtendedTemplate(self.template).safe_substitute(keys.get())
            m=(GlobalPattern.templateDynamicPattern).matcher(template)
            if m.find():
                prefix, module, method, params=m.group(1), m.group(2), m.group(3), m.group(4) or None
                try:
                    suffix=getattr(macros[module], method)(params) if params else getattr(macros[module], method)()
                    self.lastTemplate="%s%s" % (prefix, suffix)
                    logger.debug('getDynamicTemplate() - [suffix=%s][prefix=%s][lastTemplate=%s]"' % (
                    suffix, prefix, self.lastTemplate))
                except Exception, x:
                    raise MySyntaxError(
                        'FATAL (getDynamicTemplate) : did you define a "#!%s()" Macro? Or are you sure your parameter "%s" exists?\n%s' % (
                        module, params or '', x))

        logger.trace('Line.getDynamicTemplate() - TEMPLATE: "%s"' % (self.lastTemplate))
        return self.lastTemplate

    def getLastTemplate(self):
        return self.lastTemplate

    def isMemorized(self):
        return self.memorizeCommand

    def getMemorizedValues(self):
        return self.memorizedValues


class ScenarioFile:
    line_pattern=Pattern.compile('^([^.]+)\.([^\|]+)\|\|([^;]+)(.*)')
    SUPPORTED_VERSION=(10, 11)

    def __init__(self, datafilepath, filein, scenarioId=0):

        self.scenarioId=scenarioId
        self.input_file=filein.strip()
        self.lines=[]
        self.datafilepath=datafilepath
        self.name=None

        # Standard=synchronous, Queued=Asynchronous
        self.type='Standard'

        # implementation/protocol dictionary
        self.loaded_implementations={}

        self.macros=None
        self.macros_definition=None

        # Only definition
        self.context_definition=None

        self.filename='%s%s%s' % (datafilepath, os.sep, filein)
        if os.path.exists(self.filename):
            self.scenario_lines=open(self.filename, 'r').readlines()
        else:
            logger.error(
                'FATAL: Scenario file "%s" does not exist, check your configuration: inFile,oneFileByThread, oneFileByProcess' % (
                    self.filename))
            raise MySyntaxError(
                'FATAL: Scenario file "%s" does not exist, check your configuration: inFile,oneFileByThread, oneFileByProcess' % (
                    self.filename))

        # asynchronous definition 
        self.asynchronous=False
        self.async_steps_count=0
        # -1 : no timeout
        self.asyncTimeout=-1
        # use the callback context Manager or not 
        self.use_contextManager=False

        # default version
        self.version=11
        if self.input_file.lower().split('.')[-1] == 'yaml' or (self.scenario_lines[0].find('#!yaml') >= 0):
            self.parse_yaml(self.filename, True)
        else:
            logger.error('[Scenario: %s] with [extension=%s] was not found !' % (
            self.input_file, self.input_file.lower().split('.')[-1]))
            raise MySyntaxError('[Scenario: %s] with [extension=%s] was not found !' % (
            self.input_file, self.input_file.lower().split('.')[-1]))

    def getName(self):
        return self.name

    def getScenarioId(self):
        return self.scenarioId

    def getAsyncTimeout(self):
        return self.asyncTimeout

    def getContextDefinition(self):
        return self.context_definition

    def getAsyncStepsCount(self):
        return self.async_steps_count

    def isAsynchronous(self):
        return self.asynchronous

    def getType(self):
        return self.type

    def __repr__(self):
        return '[name=%s][filein=%s][filename=%s]' % (self.getName(), self.input_file, self.filename)

    def get_array_lines(self):
        return self.lines

    def isLastStepAsync(self):
        return self.lines[-1].isAsynchronous()

    def getMetadata(self):
        return self.loadedMacros

    #     def format(self):
    #         '''
    #           format an object ScenarioFile to a Yaml string representation
    #           TODO : valid only for format 1.0 - do we maintain ?
    #         '''
    #         o=[]
    #         macros=[]
    #         for f in self.CachedMacros:
    #             macros.append(f)
    #         o.append({ 'macros' : macros })
    #         for line in self.lines:
    #             w ={ 'protocol': line.protocol, 'template':line.template, }
    #             v={}
    #             for j, field in enumerate(line.fields):
    #                 v['VAR%02d' % (j)]=field.getValue()
    #             w['input'] = dict(v)
    #             v={}
    #             if line.isMemorized():
    #                 #
    #                 for memfield in line.getMemorizedValues():
    #                     v[memfield.name]='%s(%s)' % (memfield.matcher_type,memfield.matcher_param) if memfield.yaml else memfield.regexp_key
    #                 w['output'] = dict(v)
    #             o.append(dict(w))
    #         return o

    def __load_protocol(self, protocol):
        '''
           Store the Classobj implementation in a cache.  
           :param protocol:
        '''
        if not self.loaded_implementations.has_key(protocol):
            self.loaded_implementations[protocol]=load_protocol(protocol)
        return self.loaded_implementations[protocol]

    def __process_recursive_includes(self, stepsList, context, includeFilesList, macros, scenarioId):

        returnedStepList=[]
        for step in stepsList:
            if 'include' in step:
                # This step is an include: we will parse the file to include, 
                # adds its steps to the current scenario's tests, merges its context with the current context, add also the macros dependencies
                fileNameToInclude=step['include']

                # We check that there is no loop in the included files
                if fileNameToInclude in includeFilesList:
                    raise Exception(
                        'Infinite loop in includes: %s' % ' > '.join(includeFilesList + [fileNameToInclude]))

                includedFileFullPath='%s%s%s' % (self.datafilepath, os.sep, fileNameToInclude)
                logger.debug('File %s will be included in %s' % (includedFileFullPath, includeFilesList[-1]))
                yaml_payload=self.parse_yaml(includedFileFullPath, False)
                for param in yaml_payload:
                    if 'macros' in param:
                        if macros:
                            macros.update(scenarioId, param['macros'])
                        else:
                            macros_definition=param['macros']
                            macros=CachedMacros(scenarioId, macros_definition)

                    if 'scenario' in param:
                        includedScenarioDic=dict(param['scenario'])

                        # We merge the current context with the context of the included file
                        # For the context variable which are defined in both context and includedContext, we use the value of context
                        includedContext=to_flattened_dictionary(dict(includedScenarioDic.get('context', {}) or {}))
                        includedContext.update(context)

                        includedStepList=list(includedScenarioDic['steps']) if ('steps' in includedScenarioDic) else []
                        includedStepList, context, macros=self.__process_recursive_includes(includedStepList,
                                                                                            includedContext,
                                                                                            includeFilesList + [
                                                                                                fileNameToInclude],
                                                                                            macros, scenarioId)

                        returnedStepList+=includedStepList
            else:
                returnedStepList+=[step]
        return returnedStepList, context, macros

    def validate_line(self, param, CheckList, DictCheckList, DictCheckNoneList=None):
        for checkthis in CheckList:
            if not checkthis in param:
                raise MySyntaxError("Mandatory parameter missing in yaml Structure: '%s'" % (checkthis))

        for checkthis in DictCheckList:
            if not checkthis in param:
                raise MySyntaxError("Mandatory parameter missing in yaml Structure: '%s'" % (checkthis))
            if type(param[checkthis]) != dict and type(param[checkthis]) != LinkedHashMap:
                raise MySyntaxError("'%s' in yaml Structure has to be a Dictionary!" % (checkthis))

        if DictCheckNoneList:
            for checkthis in DictCheckNoneList:
                if not checkthis in param:
                    continue
                if type(param[checkthis]) == None:
                    raise MySyntaxError(
                        "'%s' in yaml Structure has to be a Dictionary, and mustn't be None!" % (checkthis))

    def parse_version_10(self, obj):
        i=0
        for param in obj:

            # the factory functions that must be initialized for macros
            if 'macros' in param:
                self.macros_definition=param['macros']


            # this is a scenario line
            else:
                try:
                    param['implementation']=self.__load_protocol(param['protocol'])
                except MySyntaxError, x:
                    raise MySyntaxError('%s\nIn line: "%s"' % (x, str(param)))

                try:
                    self.validate_line(param, ('protocol', 'template', 'implementation'), ['input'], [])
                except MySyntaxError, x:
                    raise MySyntaxError('%s\nIn line: "%s"' % (x, str(param)))

                # please note the dict() conversion from LinkedHashMap to python dict
                self.lines.append(
                    Line(yaml_format=True, debug=self.debug, protocol=param['protocol'], template=param['template'],
                        fields=dict(param['input']), memory=dict(param).get('output', None),
                        sleep=dict(param).get('sleep', '0'), implementation=param['implementation']))
                i+=1

    def parse_version_11(self, parsed_yaml):

        # For lag management between 2 protocol [VRZ]
        last_protocol=None

        # The only list keys accepted at the 0 level
        validSet=['macros', 'version', 'scenario']
        for param in parsed_yaml:

            # To avoid confusion on keys (for instance functions instead of macros)
            if dict(param).keys()[0] not in validSet:
                raise MySyntaxError(
                    'key "%s" is invalid, they must be a subset of "%s"' % (dict(param).keys()[0], validSet))

            # the functions that must be initialized for macros
            if 'macros' in param:
                self.macros_definition=param['macros']
                self.macros=CachedMacros(self.scenarioId, self.macros_definition)

            if 'scenario' in param:
                # Now we have a scenario dictionary with 3 keys name,context,steps
                # please note the dict() conversion from LinkedHashMap to python dict
                param1=dict(param['scenario'])

                # update scenario with name
                self.name=param1.get('name')

                # if context key exist but is None, set to {}
                # Flatten the dictionary if there are sub dictionary
                self.context_definition=to_flattened_dictionary(dict(param1.get('context', {}) or {}))

                # call recursive include substitution
                # include are scenario files (to have context and right indentation syntax)
                evaluated_steps, self.context_definition, self.macros=self.__process_recursive_includes(
                    list(param1['steps']), self.context_definition, [self.input_file], self.macros, self.scenarioId)

                # Look at each steps
                for i, step1 in enumerate(evaluated_steps):
                    step=dict(step1)

                    if 'protocol' not in step:
                        step['protocol']='dummy'

                    # get implementation preloaded class object (ClassObj)
                    logger.trace('Loading implementation %s' % (step['protocol']))
                    try:
                        step['implementation']=self.__load_protocol(step['protocol'])
                    except MySyntaxError, x:
                        raise MySyntaxError(
                            '%s\nwhile parsing file %s, In line: "%s"' % (x, self.input_file, str(step)))

                    #
                    # case: we want to sent multiple message to contextManager
                    #       this can be done ONLY with blocking=False
                    #
                    if 'async' in step and isinstance(step['async'], ArrayList):
                        logger.trace('Multi contextKey structure')
                        d=dict()
                        d['blocking']=False
                        d['contextKey']={}
                        d['timeout']={}
                        d['multipleCaller']=True
                        for k in step['async']:
                            if 'contextKey' in k:
                                value=k.get('value') or k.get('contextValue')
                                if value:
                                    m=GlobalPattern.dynPlaceholderPattern.matcher(self.contextValue)
                                    if m.find():
                                        value=m.group(1)
                                d['contextKey'][k['contextKey']]=value
                                # 5 minutes by default if not defined
                                d['timeout'][k['contextKey']]=int(k.get('timeout') or 300)
                                if k.get('blocking'):
                                    raise SyntaxError('Multiple async calls cannot be compatible with "blocking=True"')
                                k['blocking']=True
                        step['async']=d
                        logger.trace('New async entry: %s, type: %s' % (str(step['async']), type(step['async'])))

                    try:
                        async_definition=dict(step.get('async', {}))
                    except Exception, e:
                        raise SyntaxError(
                            'Invalid definition of the key "async", should be a dict, got[value=%s] [type=%s], error=%s' % (
                            step['async'], type(step['async']), e))
                    if async_definition:
                        #
                        # We could have a callback protocol not defined in the 'protocol' keys for a step,
                        # because call_protocol are used for post-processing of asynchronous steps.
                        #
                        if 'callback_protocol' in async_definition:
                            try:
                                self.__load_protocol(async_definition['callback_protocol'])
                            except MySyntaxError, x:
                                raise MySyntaxError(
                                    '%s\n Error loading protocol %s while parsing file %s, In line: "%s"' % (
                                    x, async_definition['callback_protocol'], self.input_file, str(step)))

                        # (Validation) count the number of async steps on all scenarios to manage number of runs 
                        if async_definition.get('blocking', True):
                            self.async_steps_count+=1
                            self.asynchronous=True
                            try:
                                self.asyncTimeout=max(self.asyncTimeout, float(async_definition['timeout']))
                            except:
                                raise MySyntaxError('"timeout" parameter is mandatory for "async" step definition')

                    logger.debug('Line number %d, Scenario initialization, asynchronous=%s, async_definition="%s"' % (
                    i, self.asynchronous, str(async_definition)))
                    # step name    
                    nameStep=step.get('name', 'NotNamedStep%d' % i)

                    # Optional feature: steps could be ignored by configuration
                    if BaseConfiguration.ignoreOptionalSteps:
                        optional=step.get('optional', False)
                        if optional:
                            logger.info(
                                'Step %s is IGNORED because marked as optional and parameter grindertool.steps.ignore=True' % (
                                    nameStep))
                            continue

                    # tags: some steps could be ignored by configuration
                    tags=step.get('tags', None)
                    if tags and BaseConfiguration.tagsListToIgnore:
                        setIgnored=set(BaseConfiguration.tagsListToIgnore.strip().split(','))
                        logger.debug('Ignored Set by configuration: "%s"' % setIgnored)

                        if isinstance(tags, str) or isinstance(tags, unicode):
                            setTags=set(tags.split(',')) if tags.find(',') > 0 else set([tags])
                        elif isinstance(tags, ArrayList):
                            setTags=set(list(tags))
                        else:
                            raise SyntaxError(
                                'Incorrect type for tags. Found "%s" should be a list or a string' % (tags))
                        logger.debug('Tags ignored on step %s: "%s"' % (nameStep, setTags))

                        try:
                            # There is a mystery here set1.intersection(set2) is not working ... So replacing by an eqquivalent
                            intersection=[k for k in setTags if k in setIgnored]
                            if intersection:
                                logger.info('Step "%s" tags "%s" are ignored by the property "%s"="%s"' % (
                                nameStep, tags, BaseConfiguration.IGNORE_TAGS, BaseConfiguration.tagsListToIgnore))
                                continue
                        except TypeError:
                            logger.error('Incompatible types setIgnored="%s" and setTags="%s"' % (setIgnored, setTags))
                            raise

                    try:
                        assertionList=list(step.get('assert', {}))
                    except ValueError:
                        raise SyntaxError(
                            '[step=%s] "key assert" must be a list with "-" character - review yaml syntax' % nameStep)

                    try:
                        teardownList=list(step.get('teardown', {}))
                    except ValueError:
                        raise SyntaxError(
                            '[step=%s] key "teardown" must be a list with "-" character - review yaml syntax' % nameStep)

                    try:
                        fieldsDictionary=dict(step.get('input', {}))
                    except ValueError:
                        raise SyntaxError(
                            'Incorrect fields definition. [step=%s] The fields of tag "input" must be dictionary entries.' % nameStep)

                    #
                    # Add keyword "memorize"
                    # Only one key is accepted among "output","memorize"
                    #
                    memorizeKey=''
                    memorizeKeyList=set(step.keys()) & set(['output', 'memorize'])
                    if len(memorizeKeyList) > 1:
                        raise SyntaxError('Only one key "output","memorize" is accepted in a step')
                    if len(memorizeKeyList) == 1:
                        memorizeKey=memorizeKeyList.pop()

                    try:
                        memoryDictionary=dict(step.get(memorizeKey, {}))
                    except ValueError:
                        raise SyntaxError(
                            '[step=%s] The "output" or "memorize" tag must be dictionary entries.' % nameStep)

                    line=Line(context=self.context_definition, yaml_format=True, noLine=i, protocol=step['protocol'],
                              last_protocol=last_protocol, implementation=step['implementation'],
                              template=step.get('template', None), template_type=step.get('template_type', None),
                              stopOnError=step.get('stopOnError', False), async=async_definition,
                              fields=fieldsDictionary, memory=memoryDictionary, assertion=assertionList,
                              teardown=teardownList,
                              testname=nameStep, sleep=dict(step.get('sleep', {})))

                    last_protocol=step['protocol']

                    # if only one step is asynchronous and using external soap call callback (context manager), the scenario is marked as using it
                    if line.isAsynchronous() and not self.use_contextManager:
                        # Ok - the context manager is at least used for one test
                        if line.use_contextManager:
                            self.use_contextManager=True

                    self.lines.append(line)

    def parse_yaml(self, fullpath, buildLinesAndContext):
        """
        Parse a Yaml scenario file. This create all the internal object model from the Yaml structure.
        One trick to not forget - the Java dictionaries are not Python dictionaries - so convert dictionaries with dict() call
        :param fullpath:
        """
        yaml=Yaml(Constructor(), Representer(), DumperOptions(), CustomResolver())
        try:
            data=open(fullpath, 'r').read()
        except:
            logger.error('Error opening file "%s"' % (fullpath))
            raise

        try:
            yaml_payload=yaml.load(data)
        except (MarkedYAMLException, YAMLException, ParserException, ReaderException, ScannerException), e:
            logger.error('Error while parsing YAML-file "%s":\n%s' % (fullpath, e))
            raise MySyntaxError('Error while parsing YAML-file "%s":\n%s' % (fullpath, e))

        #CSS: The following test is causing regression for IDCloud projects
        #if not isinstance(yaml_payload, list):
        #    raise SyntaxError('The YAML file must be a list !')

        for param in yaml_payload:
            # Do we have version ?
            if 'version' in param:
                self.version=int(param['version'].replace('.', ''))
                break

        if self.version not in self.SUPPORTED_VERSION:
            raise MySyntaxError('Scenario version has to be one of: "%s"' % (str(self.SUPPORTED_VERSION)))

        # Well we use python power
        if buildLinesAndContext:
            logger.trace('Parsing %s and building scenariofile' % fullpath)
            getattr(self, 'parse_version_' + str(self.version))(yaml_payload)
        else:
            logger.trace('Parsing %s without building scenariofile' % fullpath)
            return yaml_payload
