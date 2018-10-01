'''
Created on Oct 10, 2010

@author: omerlin
'''
from java.lang import Exception as JavaException
from java.util.regex import Pattern
import os
from string import Template
import sys
import traceback
import types

from corelibs.coreGrinder  import CoreGrinder
#----------------------------------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


def checkProperty(param, mandatory=True):
    value = properties.getProperty(param) or None
    if not value:
        if mandatory:
            logger.error('Property "%s" is MANDATORY in grindertool property file' % (param))
    logger.trace('checkProperty(%s)=>"%s"' % (param, str(value)))
    return value

def checkPropertyList(paramList, mandatory=False):
    value=None
    for k in paramList:
        value=checkProperty(k, mandatory)
        if value:
            return value
    return value


def checkPropertyFile( param, warning=False):
    filename=checkProperty(param)
    if filename:
        if not os.path.exists(filename):
            if warning:
                logger.warn('[current directory: "%s"] Not Found path (or file) "%s" on required parameter "%s"' % (os.getcwd(), filename, param))
            else:
                logger.error('[current directory: "%s"] Invalid path (or file) "%s" on required parameter "%s"' % (os.getcwd(), filename, param))
                raise SyntaxError('[current directory: "%s"] Invalid path (or file) "%s" on required parameter "%s"' % (os.getcwd(), filename, param))
    return filename


def load_module(cl, userlib='implementations'):
    try:
        module='%s.%s' % (userlib, cl)
        logger.debug('Loading python module "%s" ' % (module))
        return __import__('%s' % (module), fromlist=['%s' % (cl)])
#         return __import__('%s' % (module))
    except (Exception, JavaException), x:
        logger.error('Module %s was not found in "%s" subdirectory' % ( cl, userlib))
        # traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))
        logger.error(errorMsg)
        #
        if isinstance(x,JavaException):
            logger.error('We have a java exception:')
            raise JavaException(x)
        raise


def load_protocol(cl, userlib='implementations'):
    
    mod=load_module(cl)
    
    # Instance of the class
    try:
        instance=getattr(mod, '%s' % (cl))
        logger.debug('load_protocol(): instance="%s"' % (instance))
        return instance
    except (Exception, JavaException), x:
        logger.error('Class "%s" must be defined in the module "%s" in package directory "%s"' % (cl,mod, userlib))
        # traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))
        logger.error(errorMsg)
        if isinstance(x,JavaException):
            logger.error('We have a java exception:')
            raise JavaException(x)
        raise
    
# def load_protocol_old(protocol):
#     ret_module=None
#     logger.debug('Loading python module "%s" ' % (protocol))
#     try: 
#         myModule = getattr(implementations, protocol)
#     except (Exception, JavaException), x:
#         logger.error('Implementation failed, reason: %s' % (x))
#         # traceback
#         exc_type, exc_value, exc_traceback = sys.exc_info()
#         errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))
#         logger.error(errorMsg)
#         #
#         if isinstance(x,JavaException):
#             raise Exception(x)
#         raise
# 
#     if isinstance(myModule, types.ModuleType):
#         logger.debug('Loading implementation class "%s" in python module "%s"' % (str(myModule), protocol))
#         try:
#             ret_module = getattr(myModule, protocol)
#             logger.debug( 'protocol "%s" loaded in local cache.' % (protocol))
#         except Exception, x:
#             raise SyntaxError('Unable to find instance for protocol "%s - %s"' % (protocol, x))
#     return ret_module


class GlobalPattern:
    '''
       Factorization of some common regexp pattern
    '''
    staticFieldPattern = Pattern.compile(r'(&&(\w+)\.(\w+)\(([^\)]*)\))')
    dynFieldPattern = Pattern.compile(r'&{0,1}([a-zA-Z]{1}[_a-zA-Z0-9]+)\.(\w+)\((.*)\)')
    templateDynamicPattern = Pattern.compile(r'(\w+)&(\w+)\.(\w+)\((.*)\)')
    memorizedVariablePattern = Pattern.compile(r'(@\w+@)')
    dynPlaceholderPattern = Pattern.compile(r'\$\{([\w\.]+)\}')
    evalPattern=Pattern.compile(r'\(([^\)]*)\)')


class ExtendedTemplate(Template):
    '''
    We use placeholder template substitution a lot
    but the default pattern does not contain the dot '.' character that we use a lot
    so simply extend the regexp to add this character. 
    '''
    idpattern = r'[_a-zA-Z][\._a-zA-Z0-9]*'

