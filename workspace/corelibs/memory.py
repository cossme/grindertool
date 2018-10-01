"""
    Memorization management part 
"""
from threading import Condition
from java.io import StringReader
from java.util.regex import Pattern
from javax.xml.parsers import DocumentBuilderFactory
from javax.xml.xpath import XPathConstants
from javax.xml.xpath import XPathFactory
from org.xml.sax import InputSource

from corelibs.coreGrinder  import CoreGrinder


#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------



class MemoryField:
    std_type=set(('regexp','xpath'))
    list_type=set(('context','context_list','context_single','list'))
    dict_type=set(('context_dict','dictionary'))
    def __init__(self, name, attributes):
        logger.debug('MemoryField() - attributes = "%s", type=%s' % (attributes,type(attributes)))
        self.matcher_type=None
        self.matcher_param=None
        self.compilation=None
        self.name=name
        self.xpathFactory = XPathFactory.newInstance()
        if isinstance(attributes, str) or isinstance(attributes, unicode):
            self.matcher_from=attributes[2:-1] if attributes[0:2]=='${' else attributes
        elif isinstance(attributes, dict):
            # Yaml format
            # The memory key
            tupple=('type','match','from','regexp','xpath')
            if not set(attributes).issubset(set(tupple)):
                logger.error('Yaml output not well defined - missing one of key "%s"' % (str(tupple)))
                raise SyntaxError('Yaml output not well defined - missing one of key "%s"' % (str(tupple)))
            self.matcher_type=attributes.get('type',None)
            self.matcher_param=attributes.get('match',None)
            self.matcher_from=attributes.get('from',None)
            if self.matcher_from:
                self.matcher_from=self.matcher_from[2:-1] if self.matcher_from[0:2]=='${' else self.matcher_from
            matcher_regexp=attributes.get('regexp',None)
            matcher_xpath=attributes.get('xpath',None)
            if matcher_regexp:
                self.matcher_type='regexp'
                self.matcher_param=matcher_regexp
            if matcher_xpath:
                self.matcher_type='xpath'
                self.matcher_param=matcher_regexp
            
            
            if self.matcher_type:
                # checking authorized type list
                all_types=self.__class__.std_type|self.__class__.list_type|self.__class__.dict_type
                if self.matcher_type not in all_types:
                    logger.error('Yaml "output" "type" key (type=%s) must be one of the element in the set: %s ' % (self.matcher_type, all_types))
                    raise SyntaxError('Yaml "output" "type" key (type=%s) must be one of the element in the set: %s ' % (self.matcher_type, all_types))
        
            #
            # pre-compilation
            #
            if self.matcher_param:
                if self.matcher_type == 'xpath':
                    xpathRegExp=self.matcher_param.replace('/text()','')
                    try:
                        logger.trace('[xpath][memfield=%s] Compiled Xpath expression: %s ' % (self.name, xpathRegExp))
                        self.compilation=self.xpathFactory.newXPath().compile(xpathRegExp)
                    except Exception,e:
                        logger.error('[xpath] Unable to compile memfield %s, reason: %s' % (self, e))
                        raise SyntaxError('[xpath] Unable to compile memfield %s, reason: %s' % (self,e)) 
                else:
                    # regexp in all other case
                    try:
                        self.compilation=Pattern.compile(self.matcher_param)
                    except Exception, e:
                        logger.error('Unable to compile memfield %s, reason: %s' % (self,e))
                        raise SyntaxError('Unable to compile memfield %s, reason: %s' % (self,e))

                 
        else:
            logger.error('yaml output attributes for key "%s" must be a dictionary or a string, found type %s' % (name, type(attributes)))
            raise SyntaxError('yaml output attributes for key "%s" must be a dictionary or a string, found type %s' % (name, type(attributes)))
        
        
        logger.debug('Added a MemoryField: %s'  % (self))



    def __repr__(self):
        return '[name=%s][type=%s][match=%s][from=%s]' % (self.name, self.matcher_type, self.matcher_param, self.matcher_from) 



class MemoryMgr:
    mutex=Condition()
    def __init__(self,dataFilePath):
        self.loadedVariable = {}
        self.dataFilePath = dataFilePath
        self.memorizedData = {}
        self.__class__.mutex.acquire()
        self.docBuilderFactory = DocumentBuilderFactory.newInstance()
        self.__class__.mutex.release()
        
    def __str__(self):
        ''' Return a string representation of MemoryMgr object.
        '''
        strTmp = "MemoryMgr object representation is : \n"
        for memVar in self.memorizedData:
            strTmp = strTmp + "  * memorizedData{%s ; %s}" % (memVar, self.memorizedData[memVar]);
        return strTmp;
    
    def getMemorizedData(self):
        return self.memorizedData
    
    def reset(self):
        self.memorizedData = {}
                  

    def __logResult(self, retcode, memfield):
        if retcode:
            logger.debug('Memorization: Extracted "%s" using pattern %s' % (retcode, memfield))
        else:
            logger.warn('Memorization: Nothing match the pattern %s' % (memfield))

    def memorizeVariable(self, memList, searchStr, respDict):
        """
            memorize a variable value found by a pattern inside a string (searchStr) - regexp of Xpath
            or
            memorize the interesting response keys (matching a criteria) from the "respDict" parameter (a dictionary)

        @param memList: a list of MemoryField object
        @param searchStr:  a SUT response string
        @param respDict: all the response dictionary (include the searchStr - which is a respDict['responseText'] value
        """
        self.docBuilder = None
        
        logger.debug('Looking pattern "%s" inside body output [%s]' % (memList, searchStr))
        for memfield in memList:
            
            logger.debug('## Looking for "%s"' % memfield)

            if memfield.matcher_from:
                try:
                    searchStr=respDict[memfield.matcher_from]
                    logger.trace('memorizeVariable() - searchStr: "%s"' % searchStr)
                except KeyError:
                    logger.error('memorizeVariable() - Unknown key "%s"' % memfield.matcher_from)
                    raise
                
            if not memfield.matcher_type:
                self.memorizedData[memfield.name] = searchStr
                if logger.isTraceEnabled():
                    logger.trace('memorizeVariable - memorized ["%s"="%s"] into "%s"' % ( memfield.matcher_from, self.memorizedData[ memfield.name], memfield.name))                
                continue
            
            if logger.isTraceEnabled():
                logger.trace('memorizeVariable() - matcher_type="%s"' % (memfield.matcher_type))
            
            if memfield.matcher_type == 'regexp' and memfield.compilation:
                m = memfield.compilation.matcher(str(searchStr))
                if m.find():
                    found=m.group(1)
                    self.memorizedData[ memfield.name] = str(found)
                    logger.debug('Extracted "%s" using pattern %s' % (found, memfield))
                else:
                    logger.warn('Nothing match the pattern %s - a group must exists in the regexp pattern' % (memfield))

            elif memfield.matcher_type == 'xpath' and memfield.compilation:
            
                xmlIStream = InputSource(StringReader(searchStr))
                if not self.docBuilder:
                    self.docBuilder = self.docBuilderFactory.newDocumentBuilder() 
                
                doc = self.docBuilder.parse(xmlIStream)
                nodes = memfield.compilation.evaluate(doc, XPathConstants.NODESET)
                nodes_length=nodes.getLength()
                if nodes_length>1:
                    logger.error('xpath %s matches more than 1 node, modify the xpath in the input file' % (memfield))
                    raise SyntaxError('xpath %s matches more than 1 node, modify the xpath in the input file' % (memfield))
                elif nodes_length==1:
                    self.memorizedData[ memfield.name] = str(nodes.item(0).getTextContent()) or ''
                    logger.debug('Extracted "%s" using pattern %s' % (self.memorizedData[ memfield.name], memfield))
                else:
                    logger.error('xpath %s NOT FOUND,nothing has been returned' % (memfield))
                    raise SyntaxError('xpath %s NOT FOUND,nothing has been returned' % (memfield))
            
            elif memfield.matcher_type in ('context' , 'context_single' , 'context_list') and memfield.compilation:
                #
                # Extract from a context dictionary all the values that match a key and store them as a list of values   
                # in yaml : 
                #          output:
                #            fieldX:
                #              type: context | context_single | context_list
                #              match: ZZZ
                # will result in storing in the memory dictionary key "fieldX" as a list of values matching "ZZZ" in the context dictionary keys.
                # if type=="context_single", the list is reduced to one element, the first one
                # otherwise this is a list.
                # type "context" is the same as type "context_list"
                #
                retcode=[respDict[key] for key in respDict.keys() if memfield.compilation.matcher(key).find()]
                if memfield.matcher_type == 'context_single':
                    if len(retcode)>1:
                        logger.warn('memorization: potential "too many error" mismatch with this memfield: %s' % (memfield))
                    retcode=str(retcode[0]) if retcode else ''
                self.__logResult(retcode, memfield)
                self.memorizedData[ memfield.name] = retcode
            
            elif memfield.matcher_type in ( 'context_dict', 'dictionary') and memfield.compilation:
                #
                # extract the sub dictionary that match a key from a context
                # in yaml :
                #          output:
                #            fieldX:
                #              type: context_dict | dictionary
                #              match: YYYY
                # will result in storing in the memory dictionary key "fieldX" a sub dictionary matching "YYYY"                
                #
                retcode=dict((key,value) for key,value in respDict.iteritems() if memfield.compilation.matcher(key).find())
                self.__logResult(retcode, memfield)
                self.memorizedData[ memfield.name] = retcode



    
