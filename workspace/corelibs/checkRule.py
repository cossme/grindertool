'''
Created on 31 juil. 2014

@author: omerlin
'''

# regular python libraries
from java.util.regex import Pattern
from javax.xml.xpath import XPathFactory
from corelibs.coreGrinder import CoreGrinder, MySyntaxError
from corelibs.filetoolbox import GlobalPattern

properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()


class CheckRule:
    """
      a simple checker object for assertion management on response
    """
    KEYWORDS=['matches', 'notmatches', 'contains', 'notcontains', 'equals', 'notequals', 'exists', 'macro', 'eval',
              'maxduration']

    def __init__(self, rule, deferred=False):

        # all keys must be lower case
        self.ruleDefinition=dict((k.lower(), v) for k, v in dict(rule).iteritems())

        # Only one keyword is authorized
        intersect=set(self.KEYWORDS).intersection(set(self.ruleDefinition.keys()))
        if len(intersect) > 1:
            logger.error(
                'We cannot have more than one keywords "%s" in the same rule among "%s"' % (intersect, self.KEYWORDS))
            raise MySyntaxError(
                'We cannot have than one keywords "%s" in the same rule among"%s"' % (intersect, self.KEYWORDS))
        if len(intersect) == 0:
            logger.error('Invalid rule: missing mandatory comparison keywords. One of "%s"' % self.KEYWORDS)
            raise MySyntaxError('Invalid rule: missing mandatory comparison keywords. One of "%s"' % self.KEYWORDS)

        # the only one keyword
        self.ruleType=list(intersect)[0]
        # For Async assertion
        self.deferred='deferred' in self.ruleDefinition or deferred

        # ignoreCase for Xpath & Regexp
        self.ignoreCase='ignorecase' in self.ruleDefinition and str(self.ruleDefinition['ignorecase']).lower() in (
        'y', 'yes', 'true')
        # For "not" expression (notequals, notcontains ...)
        self.positiveCheck=True
        # if there is a ${VAR} template
        self.isPlaceholder=False
        # "equals" rule are special "contains" rule
        self.equalsRule=False

        # For Regexp rules
        self.isCompiledRule=False
        self.compiledRule=None
        self.regexpExpression=None

        # For Xpath rules        
        self.hasXpath=False
        self.xpathExpression=None
        self.textQuery=False
        self.isXpathPlaceholder=False
        self.compiledXpathRule=None
        self.isXpathCompiledRule=False

        # duration rule
        if 'maxduration' in self.ruleDefinition:
            try:
                s_duration=self.ruleDefinition['maxduration'].strip()
                self.maxDuration=int(s_duration)
            # this means that we have a string
            # see if we have the
            except ValueError:
                try:
                    if s_duration[-2:] == 'ms':
                        self.maxDuration=int(s_duration[:-2])
                    elif s_duration[-1:] == 's':
                        self.maxDuration=int(s_duration[:-1]) * 1000
                except Exception, e:
                    raise MySyntaxError(
                        'Invalid rule: maxDuration must be expressed in milliseconds (ms) or seconds (s), raised: %s' % str(
                            e))

            return

        #
        # quoted string may be forced in both "equals" and ("regexp","contains") keywords
        # default behavior is:
        #  "equals"             :  literal_usage=True
        #  "regexp","contains"  :  literal_usage=False
        # default behavior is superseded by the usage of the keywords "literal","quote_string","regexp"
        # 
        # Change: for **equals** keyword, "quoted" is the default
        #
        # We force the literal usage (quoted string) in the case of equals
        self.equalsRule=self.ruleType.lower().find('equals') >= 0
        self.literal_usage=True if self.equalsRule else False

        if len(list(set(self.ruleDefinition) & set(['literal', 'quote_string', 'regex']))) > 1:
            logger.error(
                'Only 1 of [literal, quote_string, regex] is accepted - please review test scenario - assertion %s' % self.ruleDefinition)
            raise MySyntaxError(
                'Only 1 of [literal, quote_string, regex] is accepted - please review test scenario - assertion %s' % self.ruleDefinition)

        #
        # This is a special case where you have complex literal values to compare (for instance quoted Http response)
        # Default is False. *** Activated if "literal: True" or quote_string: True in the Assertion rule ***
        #
        if 'literal' in self.ruleDefinition:
            self.literal_usage=self.ruleDefinition.get('literal')
        if 'quote_string' in self.ruleDefinition:
            self.literal_usage=self.ruleDefinition.get('quote_string')
        if 'regex' in self.ruleDefinition:
            #   
            # for not literal_usage to False if regex is explictly specified in rule def   
            # for example:  - { response_key: toto, equals: 't[a-z]+', regex: True }
            #                        
            self.literal_usage=not self.ruleDefinition.get('regex')

        # -------------
        # macro keyword
        # -------------------------
        self.isMacroRule=False
        if self.ruleType == 'macro':
            #
            self.isMacroRule=True
            self.macroExpression=self.ruleDefinition['macro']
            # We check the macro format
            if not GlobalPattern.dynFieldPattern.matcher(self.macroExpression).find():
                raise SyntaxError(
                    'The macro "%s" format is incorrect, it is not a macro of the form module.function(parameter)' % self.ruleDefinition['macro'])
            logger.trace('"macro" rule to evaluate: %s' % (self.ruleDefinition['macro']))
            return

        # -------------
        # eval keyword
        # -------------------------
        self.isEvalRule=False
        self.stringToEvaluate=''
        if self.ruleType == 'eval':
            self.isEvalRule=True
            self.stringToEvaluate=self.ruleDefinition['eval']
            logger.trace('"eval" rule to evaluate: %s' % (self.ruleDefinition['eval']))
            return

            # Identify the response key to compare to
        self.responseKey=self.ruleDefinition['response_key'] if 'response_key' in self.ruleDefinition else \
        self.ruleDefinition['from'] if 'from' in self.ruleDefinition else 'responseText'

        # we remove any placeholder in the response key
        m=(GlobalPattern.dynPlaceholderPattern).matcher(self.responseKey)
        if m.find():
            self.responseKey=m.group(1)

        # -------------
        # exists keyword
        # allows to check that a rule.responseKey exists or not
        # -------------------------
        if self.ruleType == 'exists':
            return

        # -----------------
        #  Xpath rule     
        # -----------------
        if 'xpath' in self.ruleDefinition:
            self.hasXpath=True
            self.xpathExpression=self.ruleDefinition['xpath']
            self.textQuery=self.xpathExpression.find('/text()') >= 0
            # To avoid NOT_FOUND in scenario checkResponse
            self.xpathExpression=self.xpathExpression.replace('/text()', '')
            self.isXpathPlaceholder=GlobalPattern.dynPlaceholderPattern.matcher(self.xpathExpression).find()
            if not self.isXpathPlaceholder:
                self.isXpathCompiledRule=True
                try:
                    xpathFactory=XPathFactory.newInstance()
                    self.compiledXpathRule=xpathFactory.newXPath().compile(self.xpathExpression)
                    logger.trace(
                        'Compiled Xpath %s has id: %s' % (self.xpathExpression, hex(id(self.compiledXpathRule))))
                except:
                    logger.error('Unable to compile xpath rule %s' % (self.xpathExpression))
                    raise MySyntaxError('Unable to compile  xpath rule %s' % (self.xpathExpression))

        # positive or not ?
        self.positiveCheck=not self.ruleType.find('not') >= 0

        # In case of "equals", we may have "space" characters ... so we don't strip 
        self.regexpExpression=self.ruleDefinition[self.ruleType] if self.equalsRule else self.ruleDefinition[
            self.ruleType].strip()

        self.isPlaceholder=(GlobalPattern.dynPlaceholderPattern).matcher(self.ruleDefinition[self.ruleType]).find()

        # ---------------
        # JSON rule
        # ----------------
        self.jsonRule=self.ruleDefinition.get('json', False)
        self.jsonStrict=self.ruleDefinition.get('strict', False)
        if self.jsonRule:
            logger.trace('JSON Rule declared')
            # no compilation
            # force literal usage
            self.literal_usage=True
            return

        # ---------------
        # regexp rule 
        # optimization : compile rule if there is no placeholder
        # ----------------
        if not self.isPlaceholder:

            self.isCompiledRule=True
            logger.trace(
                '[CheckRule][No placeholder=>compiling rule][equals=%s][literal=%s][value=%s][positiveCheck=%s]' % (
                self.equalsRule, self.literal_usage, self.regexpExpression, str(self.positiveCheck)))
            tmp_regexpExpression=Pattern.quote(str(self.regexpExpression)) if self.literal_usage else str(
                self.regexpExpression)
            if self.equalsRule:
                tmp_regexpExpression='^%s$' % (tmp_regexpExpression)
                logger.trace('[CheckRule][equals=%s][literal=%s][tmp_regexp=%s]' % (
                self.equalsRule, self.literal_usage, tmp_regexpExpression))
            self.compiledRule=Pattern.compile(tmp_regexpExpression,
                                              Pattern.CASE_INSENSITIVE | Pattern.DOTALL) if self.ignoreCase else Pattern.compile(
                tmp_regexpExpression, Pattern.DOTALL)

    def getXpathCompiledRule(self):
        return self.compiledXpathRule

    def hasXpathRule(self):
        return self.hasXpath

    def getCompiledRule(self):
        return self.compiledRule

    def __repr__(self):
        s='[definition="%s"][type=%s][isCompiledRule=%s][isXpathCompiledRule=%s][ignoreCase=%s][deferred=%s][hasXpath=%s]' % (
        self.ruleDefinition, self.ruleType, self.isCompiledRule, self.isXpathCompiledRule, self.ignoreCase,
        self.deferred, self.hasXpath)
        return s
