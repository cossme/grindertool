"""
  For template payload management
"""

from java.util.regex import Pattern
from java.util import LinkedHashMap
import os

# Json
from net.sf.json import JSONSerializer

# Yaml snakeyaml
from org.yaml.snakeyaml.scanner import ScannerException
from org.yaml.snakeyaml.error import MarkedYAMLException,YAMLException
from org.yaml.snakeyaml.parser import ParserException
from org.yaml.snakeyaml.reader import ReaderException
from org.yaml.snakeyaml import Yaml, DumperOptions
from org.yaml.snakeyaml.constructor import Constructor
from org.yaml.snakeyaml.representer import Representer

from corelibs.yaml_custom import CustomResolver

#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder, MySyntaxError
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

        
class Command:
    memoryPattern=Pattern.compile("@.+@")
    # old format is : [request|response]<indice>.<keyword>=<value>
    oldFormatPattern=Pattern.compile("(\w+\.)\w+")
    
    def __init__(self, templateFilePath, templateShortName, templateType):
        self.templateFilePath = templateFilePath
        self.templateShortName = templateShortName
        self.templateType=templateType
        
        # Yaml template file
        self.isYamlTemplate=False
        # The template in Yaml format 
        self.yamlTemplate=None
        
        
        if templateType in ['string','text']:
            self.templateAsString=templateShortName
            return

        # the final template file name
        file2read=''
        if templateType == 'yaml_inline':
            self.yamlTemplate=templateShortName
            self.isYamlTemplate=True
        else:
            # template in file
            file2read = '%s/%s.%s' % (self.templateFilePath, self.templateShortName, 'template')
            self._readTemplate(file2read)            
        
        #----------------------
        # Here we should have a Yaml file loaded in the variable self.yamlTemplate
        #------------------       
        
        # Store the template under the old string format
        self.templateAsString = self._convertTemplateOldFormat(file2read)  

    def _convertOldFormat(self, index, typeStr, dic):
        '''
          Factorization, for the Yaml conversion to the old format
          yaml format is :
          - request:
              uri: <an uri>
              body: <a body>
              headers:
                key1: value1
                key2: value2
            response:
              statuscode: 200
              delay_ms: 50
          - request:
            (...)
        :param index: this is the index sequence of the yaml, the sequence separator is the "-" character for a list in yaml
        :param typeStr: request or response key
        :param dic: the sub dictionary for the key request or the key response
        '''
        #request={uri=/context/create, headers={Content-Type=application/json;charset=utf-8}, body={"contextKey" : "msisdn", "value" : 334, "host" : "10.10.153.126", "port" : 3000, "expirationtime": 1456789}}, response={statuscode=200, delay_ms=20}
        try:
            dataDict=dict(dic[typeStr])
        except:
            logger.error('while loading "%s" - yaml key "%s" has to be at level0 a dictionary !' % (self.templateShortName, typeStr))
            raise MySyntaxError('while loading "%s" - yaml key "%s" has to be at level0 a dictionary !' % (self.templateShortName, typeStr))

        # Look if we have a json content
        isJson=False
        if 'headers' in dataDict:
            for name,value in dict(dataDict['headers']).iteritems():
                if name.lower() == 'content-type':
                    isJson = value.lower().find('application/json') >= 0
                    if logger.isDebugEnabled():
                        logger.debug('[name=%s][value=%s][isJson=%s]' % (name, value, isJson))

        # Solve the problem of empty lines in a SOAP http request 
        if typeStr=='request':
            if 'body' in dataDict:
                dataDict['body']='\n'.join([line for line in dataDict['body'].split('\n') if line.strip()])                

        retStr=''
        # Old format header separator (pipe) could be overloaded
        delimiter=dataDict.get('header_separator','|')
        
        for name,value in dataDict.iteritems():
            if logger.isTraceEnabled():
                logger.trace('[%s_convertOldFormat] - [name=%s][value=%s][type value=%s]' % (self.__class__.__name__,name,value,type(value)))
            
            # very unlikely
            # Avoid misunderstanding with the yaml format (if people use previous syntax request0.xxx keyword)
            m = self.oldFormatPattern.matcher(name)
            if m.find():
                name=name.replace(m.group(1),'')

            if name in ('uri'):
                value = str(value)
                
            if isinstance(value,LinkedHashMap):
                # Yaml does a strange interpretation of string for Json if you don't have a single quote around your string 
                if name == 'body':
                    value= JSONSerializer.toJSON(value) if isJson else str(value)
                elif name in 'headers':
                    s=''
                    for name1,value1 in dict(value).iteritems():
                        s+='%s:%s%s' % (name1,value1,delimiter)
                    value=s
                    
            retStr+='%s%d.%s=%s\n' % (typeStr, index , name, value)
        return retStr

    def _convertTemplateOldFormat(self, file2read):
        # now conversion to the old format
        #-----------------------------------------
        strTemplate=''
        
        # first we have a list of templates with 2 keys: request and response
        for i,templateLine in enumerate(self.yamlTemplate):
            dictTemplateLine=dict(templateLine)
            if not all(name in ('request','response') for name in dictTemplateLine.keys()):
                logger.error('Incorrect format - each level 0 list has to be a dictionary with the keys "request" and "response" while reading "%s"!'% (file2read))
                raise MySyntaxError('Incorrect format - each level 0 list has to be a dictionary with the keys "request" and "response" while reading "%s"!'% (file2read))
            
            strTemplate += self._convertOldFormat( i, 'request', dictTemplateLine)             
            strTemplate += self._convertOldFormat( i, 'response', dictTemplateLine)        
                
            logger.trace('_readTemplate[YAML]="%s"' % (strTemplate))
        return strTemplate


     
    def _readTemplate(self, file2read):
        '''
           evaluate if the template has a yaml format
        '''       
        if not self.isYamlTemplate:
            initialFile=file2read
            logger.debug('[%s._readTemplate] Looking for file: "%s"' % (self.__class__.__name__,initialFile))
            
            if not os.path.exists(file2read):
                # check both .yaml & .yml extension
                file2read='%s.yaml' % (file2read) 
                logger.debug('[%s._readTemplate] Looking for file: "%s"' % (self.__class__.__name__, file2read))
                if os.path.exists(file2read):
                    self.isYamlTemplate=True
                else:
                    file2read='%s.yml' % (file2read) 
                    logger.debug('[%s._readTemplate] Looking for file: "%s"' % (self.__class__.__name__, file2read))
                    if os.path.exists(file2read):
                        self.isYamlTemplate=True
                    else:
                        logger.error('[%s._readTemplate] Template File "%s" doesn\'t exist (even with yaml extension)' % (self.__class__.__name__,initialFile))
                        raise MySyntaxError('[%s._readTemplate] Template File "%s" doesn\'t exist (even with yaml extension)' % (self.__class__.__name__,initialFile))
                                          
            # So the template file exists            
            try:
                logger.debug('[%s._readTemplate] Reading template file "%s"' % (self.__class__.__name__,file2read))
                lines=open (file2read, 'r').readlines()
            except:
                logger.error('[%s._readTemplate] failure opening template file "%s"' % (self.__class__.__name__,file2read))
                raise MySyntaxError('[%s._readTemplate] failure opening template file "%s"' % (self.__class__.__name__,file2read))
            
            # Shebang testing for Yaml format
            if not self.isYamlTemplate and ( lines[0].find('#!yaml')>=0 or lines[0].find('#!yml')>=0) :
                self.isYamlTemplate=True

        if not self.isYamlTemplate:
            logger.error('[%s._readTemplate] compatibility issue ! template must be YAML data', (self.__class__.__name__))
            raise SyntaxError('[%s._readTemplate] compatibility issue ! template must be YAML data', (self.__class__.__name__))
                
        # Yaml format: load the string to Yaml if we don't have already
        if not self.yamlTemplate:
            yaml = Yaml(Constructor(), Representer(), DumperOptions() , CustomResolver())
            try:
                self.yamlTemplate = yaml.load(''.join(lines).strip())
            except (MarkedYAMLException, YAMLException,ParserException, ReaderException, ScannerException ) , e:
                logger.error( 'Error while parsing YAML-file "%s":\n%s' % (file2read, e))
                raise MySyntaxError( 'Error while parsing YAML-file "%s":\n%s' % (file2read, e))
            
            logger.trace("_readTemplate - Loaded Yaml : '''%s'''" % (self.yamlTemplate))
        
        # Templates are list object        
        if not isinstance(list(self.yamlTemplate),list):
            logger.error('Yaml template must be a list of dictionaries while reading "%s"!'% file2read)
            raise MySyntaxError('Yaml template must be a list of dictionaries while reading "%s"!'% file2read)


        
    
    def __repr__(self):
        return '[type=%s][content=%s]' % (self.templateType, self.templateAsString)
    
    def getStr(self):
        return self.templateAsString
        
    
    def __convert2Vars(self, str2use):
        '''
          *** still useful ? ***
        Optimized Java version
        conversion of an input string in format ${XX.string} to @VARXX where XX is 2 digits
        return the convert String
        '''
        replPattern = Pattern.compile('(\$\{(\d{1,2})\..+?})')
        match = replPattern.matcher(str2use)
        while(match.find()):
            replStr = '@VAR%02d' % int(match.group(2))
            str2use=str2use.replace(match.group(1),replStr) 
        
        return str2use
    
class TemplateManager:
    def __init__(self, templateFilePath):
        '''
          Create an store all commands in a dictionary
          Update (12/12/10): to be sure to be thread safe, loadeObjects and loadedFile has
                   been moved has instance variable (no more class variable)
        '''   
        self.templateFilePath = templateFilePath
        self.cachedTemplates = {}
        self.macros=None

    def get_or_load(self, templateType, templateShortName, macros=None):
        ''' 
            Store the template in a hash key table whose key is a template
            The value is the template content itself with 
               templateShortName : it's a template name
               templateType      : file | yaml_inline
               macros            : the macros instances
        '''
        try:
            return self.cachedTemplates[templateShortName]
        except KeyError:
            self.macros=macros
            logger.debug('Loading template "%s" into memory' % (templateShortName))
            self.cachedTemplates[templateShortName] = Command(self.templateFilePath, templateShortName, templateType) 
            return self.cachedTemplates[templateShortName]
        except Exception, e:
            logger.error('Unable to load [template=%s][type=%s], reason: %s' % (templateShortName, templateType, e))
            raise SyntaxError('Unable to load [template=%s][type=%s], reason: %s' % (templateShortName, templateType, e))

