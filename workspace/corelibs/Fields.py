from java.util import LinkedHashMap, ArrayList

from corelibs.filetoolbox import GlobalPattern, ExtendedTemplate
from corelibs.coreGrinder  import CoreGrinder

#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()

class HashArrayField:
    def __init__(self, name, dictValue):
        self.name=name
        self.listFields=[]
        self.isFunction=False
        for elemName,elemValue in dictValue.iteritems():
            aField=Field(elemName, elemValue)
            self.listFields.append( aField )
            if aField.isFunction:
                self.isFunction=True


    def __repr__(self):
        s='%s:\n' % (self.name)
        for field in self.listFields:
            s+='  %s: %s\n' % (field.name,field.value)
        return s                


class ListArrayField:
    '''
      Yaml input fields of type list of dictionary
      We manage them internally as a list of list of Field object.
    '''
    def __init__(self, listName, listValue):
        self.name=listName            
        # Flat field list
        self.listFields=[]
        self.isFunction=False
        for listElem in listValue:
            if isinstance(listElem, LinkedHashMap):
                l=list()
                for elemName,elemValue in dict(listElem).iteritems():
                    aField=Field(elemName, elemValue)
                    l.append(aField)
                    if aField.isFunction:
                        self.isFunction=True
                self.listFields.append( l )
                
    def __repr__(self):
        s=''
        for listElem in self.listFields:
            if isinstance(listElem, list):
                s+='- { '
                for elem in listElem:
                    s+= '%s : %s, ' % (elem.name,str(elem.value))
                s+='}\n'
        return s                
        
class Field:
    '''
      Field are an object used to store input dictionary element
      The reason is to pre-parse the dictionary values to know if:
      - they have a function format
      - they have a placeholder
      - or they are pure literal values
    '''
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.isFunction = False
        self.isTemplate = False
        self.isLiterral=True
        self.isFunction = (GlobalPattern.dynFieldPattern).matcher(str(value)).find()
        self.isTemplate = (GlobalPattern.dynPlaceholderPattern).matcher(str(value)).find()
        self.isLiterral=not self.isFunction and not self.isTemplate
        logger.trace('Field(): [name=%s][value=%s][isFunction=%s][isTemplate=%s][isLiterral=%s]'  % (name,value,self.isFunction,self.isTemplate,self.isLiterral) )

    def setValue(self,value):
        self.value=value
    def __repr__(self):
        return '[name=%s][value=%s][isFunction=%s][isTemplate=%s][isLiterral=%s]' % (self.name,self.value,self.isFunction,self.isTemplate,self.isLiterral)
      
      
class InputField:
    '''
      Inputfield contains input Yaml scenario entry
      Input fiels could be :
      - Field object (parsed dictionary entry )
      - ListArrayField object ( list of dictionary entry) 
      So this is a list of Field and ListArrayField object
    '''
    def __init__(self, inputFields):
        self.fields=[]
        self.isFunction=False
        for name,value in inputFields.iteritems():
            if isinstance(value, ArrayList):
                elem=ListArrayField(name,list(value))
            elif isinstance(value, LinkedHashMap):
                elem=HashArrayField( name, dict(value))
            # normal UC, the input field is a string
            else:
                elem=Field(name,value)
            self.fields.append(elem)
            if not self.isFunction:
                self.isFunction=elem.isFunction  


    def update(self, cache):
        '''
        Called from context.process() 
        an instance of InputField must be transformed to its original python format (list of dictionaries) but with
        all placeholder substituted
        :param cache: cache for placeholder substitution
        '''
        d={}
        for elem in self.fields:
            if isinstance(elem, ListArrayField):
                d[elem.name]=[]
                for sublist in elem.listFields:
                    subdict={}
                    for k in sublist:
                        subdict[k.name]=ExtendedTemplate(str(k.value)).safe_substitute(cache)
                    d[elem.name].append(subdict)
            elif isinstance(elem, HashArrayField):
                d[elem.name]={}
                for field in elem.listFields:
                    d[elem.name][field.name]=ExtendedTemplate(str(field.value)).safe_substitute(cache)
            else:
                d[elem.name]=ExtendedTemplate(str(elem.value)).safe_substitute(cache)
        return d
    
    def __repr__(self):
        s=''
        for elem in self.fields:
            s+= str(elem)
        return s
             
            
    def getAllFields(self):
        '''
         Generator to deliver Field object 
        '''
        for k in self.fields:
            if isinstance(k, ListArrayField):
                for sublist in k.listFields:
                    for elem in sublist:
                        yield elem
            elif isinstance(k, HashArrayField):
                for elem in k.listFields:
                    yield elem
            else:
                yield k

    def getLiterral(self):
        '''
        Generator to deliver literal Field element
        '''
        for k in self.fields:
            if isinstance(k, ListArrayField):
                for sublist in k.listFields:
                    for elem in sublist:
                        if elem.isLiterral:
                            yield elem
            elif isinstance(k, HashArrayField):
                for elem in k.listFields:
                    if elem.isLiterral:
                        yield elem
            else:
                if k.isLiterral:
                    yield k
            
    def getTemplate(self):
        '''
        Generator to deliver Template placeholder Field 
        '''
        for k in self.fields:
            if isinstance(k, ListArrayField):
                for sublist in k.listFields:
                    for elem in sublist:
                        if elem.isTemplate:
                            yield elem
            elif isinstance(k, HashArrayField):
                for elem in k.listFields:
                    if elem.isTemplate:
                        yield elem
            else:
                if k.isTemplate:
                    yield k

    def getFunction(self):
        '''
        Generator to deliver Field containing a function
        '''
        for k in self.fields:
            if isinstance(k, ListArrayField):
                for sublist in k.listFields:
                    for elem in sublist:
                        if elem.isFunction:
                            yield elem
            elif isinstance(k, HashArrayField):
                for elem in k.listFields:
                    if elem.isFunction:
                        yield elem
            else:
                if k.isFunction:
                    yield k
