'''
Created on 23 sept. 2014

@author: omerlin
'''

import datetime
from distutils.dir_util import copy_tree
from exceptions import SyntaxError
from java.io import FileInputStream, File
from java.lang import ClassLoader
from java.net import URLClassLoader, URL
from java.util import Properties
from os import listdir
from os.path import os, normpath, exists, isfile, isdir, join
import sys
import time

from net.grinder.common import GrinderProperties
from net.grinder.script.Grinder import grinder
from org.slf4j import LoggerFactory


logger=None
properties=None
if grinder:
    logger=grinder.getLogger()
    properties=grinder.getProperties()

class MySyntaxError(SyntaxError):
    def __init__(self, message):
        super(MySyntaxError, self).__init__(message)
        print('FATAL: %s' % (message) )


class JarSeekingURLClassLoader(URLClassLoader):
    '''
       To create a context classloader for a thread
       usage:
            originalClassLoader = Thread.currentThread().getClassLoader()
            newClassLoader = JarSeekingURLClassLoader( a_jar_directory )
            try:
               Thread.currentThread().setContextClassLoader(newClassLoader)
               (...)   
            finally:
                Thread.currentThread().setContextClassLoader(originalClassLoader)
    '''
    def __init__(self, jarfile): 
        # Call the URLClassLoader constructor
        super().__init__( JarSeekingURLClassLoader.makeUrls(jarfile) )
 
    @staticmethod
    def makeUrls(jarfile):
        urls=[]
        if isfile(jarfile) and exists(jarfile):
            urls.append[ File(jarfile).toURL() ]
        if isdir(jarfile):
            for f in listdir(jarfile):
                JarSeekingURLClassLoader.makeUrls( join(jarfile,f) )
        return urls
    

class classPathLoader :
    '''
    from http://forum.java.sun.com/thread.jspa?threadID=300557
    
    Author: SG Langer Jan 2007 translated the above Java to this
          Jython class
    Purpose: Allow runtime additions of new Class/jars either from local files or URL
       ''' 
    def addDirectory(self, directory):
        '''
           Add all the file under the "directory" to the classloader
           :param directory: initial jar directory
        '''
        for f in listdir(directory):
            jarFile=join(directory,f)
            if isfile(jarFile):
                logger.debug( 'Adding %s' % (jarFile))
                self.addFile(jarFile)
            if isdir(jarFile):
                self.addDirectory(jarFile)
                
    def addFile (self, s):
        '''
           adding a Jar file to the classloader 
        '''
        f = File (s)
        u = f.toURL ()
        a = self.addURL (u)
        return a

    def addURL (self, u):
        '''
           Reflexivity to add a jar in the system class loader
        '''
        sysloader =  ClassLoader.getSystemClassLoader()
        sysclass = URLClassLoader
        method = sysclass.getDeclaredMethod("addURL", [URL])
        # Could raise java.lang.SecurityException
        method.setAccessible(1)
        method.invoke(sysloader, [u])
        return u


def addProjectFiles(properties, logger):
    # Allows to separate a project directory
    # Take care of some side effects when dealing with agents
    projectPath=properties.get('projectPath') or None
    logger.info('addProjectFiles(): projectPath=%s' % (projectPath))
    
    
    # get the directory for data, log and template files 
    # (log file path is optional, it will be set to data file path if it doesn't exist)
    dataFilePath = properties.get('dataFilePath') or None 
    if not dataFilePath and not projectPath:
        raise SyntaxError('Mandatory Input file location parameter "dataFilePath" not defined !')
    
    # Template directory may not exists (so the optional parameter warning=True in checkPropertyFile()     
    templateFilePath = properties.get('templateFilePath') or None
    
    properties_changed=False
    if projectPath:
        
        if not os.path.exists(projectPath):
            raise SyntaxError('The directory or parameter "projectPath" unknown !')
        
        if not dataFilePath:
            dataFilePath = './data/input'
            properties['dataFilePath']=dataFilePath
            properties_changed=True
        if not os.path.exists(dataFilePath):
            raise SyntaxError('The directory or parameter "dataFilePath" unknown !')
        
        
        if not templateFilePath:
            templateFilePath = './data/templates'
            properties['templateFilePath']=templateFilePath
            properties_changed=True
        if not os.path.exists(templateFilePath):
            raise SyntaxError('The directory or parameter "templateFilePath" unknown !')    
        
        # 
        if properties_changed:
            logger.info('Saving properties ...')
            properties.save()
        
        logger.info('dataFilePath="%s"' % (dataFilePath))
        logger.info('templateFilePath="%s"' % (templateFilePath))
        logger.info('projectPath="%s"' % (os.path.abspath(projectPath)))
        logger.info('current directory: "%s"' % (os.path.abspath('.') ))
        logger.info('sys.path="%s"' % (sys.path))
        
        # Copy all files located in the alternate directory
        # TODO: Find a better method for critical resource protection between processes
        if grinder.processNumber==0:
            copy_tree(os.path.abspath(projectPath), os.path.abspath('.'))
        else:
            time.sleep(10)
           



def bootstrapLibrairies():
    if grinder:
        properties=CoreGrinder.getProperties()
        logger=grinder.logger
        
        # Copy all project files before loading Jar dependencies
        addProjectFiles(properties, logger)
        
        # A helper class to add libraries dynamically on the classloader
        cl = classPathLoader()
        
        ########## BOOTSTRAP CORE LIBRARIES #######
        currdir=properties.getProperty('grindertool.core.lib') or '%s%s%s' % (normpath(os.getcwd()), os.sep, 'libs%score' % (os.sep)) 
        if exists(currdir):
            logger.info('[agent=%d][processNumber=%d] Loading core librairies %s' % (grinder.agentNumber, grinder.processNumber, currdir))
            cl.addDirectory(currdir)
        else:
            logger.error('Configuration error: Core libs directory not found in location %s' % (currdir))
            raise SyntaxError('Configuration error: Core libs directory not found in location %s' % (currdir))
        
        
        #### OTHER LIBRARIES present under libs ####
        currdir='%s%s%s' % (normpath(os.getcwd()), os.sep, 'libs') 
        if exists(currdir):
            for a_dir in os.listdir(currdir):
                if a_dir not in ('core'):
                    logger.info('[agent=%d][processNumber=%d] Loading librairies under %s' % (grinder.agentNumber, grinder.processNumber, a_dir))
                    cl.addDirectory('%s%s%s' % (currdir,os.sep,a_dir))
                
        ########## BOOTSTRAP SMPP ###############
        #
        # Must be load only if smpp is started
        if properties.getBoolean('grindertool.smsc.start', False):
            smpp_dir=properties.getProperty('grindertool.smsc.lib') or None
            if not smpp_dir:
                logger.error('Please set required parameter: grindertool.smsc.lib')
                raise SyntaxError('Please set required parameter: grindertool.smsc.lib')
            if not os.path.exists(smpp_dir):
                logger.error('Smpp libraries directory (grindertool.smsc.lib) %s does not exist !' % (smpp_dir))
                raise SyntaxError('Smpp libraries directory (grindertool.smsc.lib) %s does not exist !' % (smpp_dir))
            logger.info('[agent=%d][processNumber=%d] Loading SMSC librairies %s ...' % (grinder.agentNumber, grinder.processNumber, smpp_dir))
            print '%s [agent=%d][processNumber=%d] Loading SMSC librairies %s ...' % (str(datetime.datetime.now()), grinder.agentNumber, grinder.processNumber, smpp_dir)
            cl = classPathLoader()
            cl.addDirectory(smpp_dir)
    # else:
    #     logger.info('No SMSC libraries loaded')
        ######################################
    
        if grinder.agentNumber==-1:
            print 'You are in STANDALONE mode (no console at all)'
            if properties.getBoolean('grindertool.smsc.start', False):
                print '\tSMSC logs location: %s%slog' % (''.join(smpp_dir.split(os.sep)[:-2] or smpp_dir.split('/')[:-2]),os.sep)
            print '\tGrindertool logs: %s' % (properties.getProperty('grinder.logDirectory'))

class MyProperties(Properties):
    '''
       Just overloading Java Properties to have same api than Grinder Properties() class entry
       This is necessary for Test class because grinder object could not be instanced without a full runtime context
    '''
    def getBoolean(self, name, default=False):
            prop=self.getProperty(name) or default
            if not prop:
                if isinstance(default, str):
                    prop=True if default.lower()=='true' else False
            return prop
            

    def getInt(self, value, default):
        return int(self.getProperty(value) or default)

    def getDouble(self, value, default):
        return float(self.getProperty(value) or default)

class MockGrinder(object):
    def __init__(self):
        self.threadNumber=10
        self.runNumber=100
        self.properties={'grinder.threads':64, 'grinder.runs':1000, 'processNumberPadding':2, 'threadNumberPadding': 4, 'runNumberPadding': 7}

    def setProperty(self, key, value):
        self.properties[key]=value
        
    def getInt(self, key, default):
        try:
            return int(self.properties[key]) if key in self.properties else default
        except:
            logger.error('MockGrinder: getInt() failed on "%s"' % (key))
            return default
        
    def getDouble(self,key,default):
        try:
            return float(self.properties[key]) if key in self.properties else default
        except:
            logger.error('MockGrinder: getDouble() failed on "%s"' % (key))
            return default
            
    def getBoolean(self,key,optional=False):  
        return True if key in self.properties and self.properties[key].lower() in ('true','yes','t','y') else False
    def get(self,key):
        return self.properties.get(key)
    
    def __iter__(self):
        return iter(self.properties.iteritems())

class CoreGrinder(object):
    '''
      Overloading of standard grinder API management in grindertool 
      to allow :
          - to redefine grinder properties
    '''
    grinderProperty=None
    
    @classmethod
    def getRealProcessNumber(cls):
        '''
         give the grinder relative process number index - because when relaunching a test the processNumber increase 
        :param cls: the calling class
        '''
        if grinder:
            return grinder.getProcessNumber() - grinder.getFirstProcessNumber()
        else:
            return 0
    
    @classmethod
    def getAgentNumber(cls):
        return grinder.getAgentNumber()
        
    @classmethod
    def getGrinder(cls):
        return grinder if grinder else MockGrinder()
    
    
    @classmethod
    def getLogger(cls):
        if grinder:
            logger=grinder.logger
            return logger
        return LoggerFactory.getLogger( 'root')
   
    @classmethod
    def getProperties(cls):
        return cls.getProperty()

    @classmethod
    def getProperty(cls):
        '''
          Load one times the overloaded property
        '''
        if not cls.grinderProperty:
            if grinder:
                cls.grinderProperty=cls.loadOtherProperties()   
            else:
                cls.grinderProperty=MockGrinder()
        return cls.grinderProperty
    
    @classmethod
    def loadOtherProperties(cls):
        '''
           include properties functionality implementation
           WARNING: adding grinder.thread, grinder.runs, grinder.process, grinder.jvm will not work in include files
                   more generally keys beginning with "grinder." prefix should be avoid because this special keys are bootstrapped in Java.
            TODO: make it recursive (low priority)
        :param cls: current class
        '''
        
        currentPath=os.getcwd()
        logger.trace('Initial properties: "%s"' % (properties))
        
        # kept one from original property file (not beginning with include keyword)
        otherKeys=GrinderProperties()
        
        # separating include from other keys
        includeKeys=[]
        noIncludeSoFar=True
        for key in properties.keys():
            if key.lower().startswith('include'):
                includeKeys.append(key)
                noIncludeSoFar=False
                continue
            otherKeys.setProperty(key,properties.getProperty(key))
        
        if noIncludeSoFar:
            logger.trace('No "include" keywords in the property file, returning properties unchanged')
            return properties

        # final properties
        newProps=GrinderProperties()

        # include, include2, include3 ... we have to order
        for key in sorted(includeKeys):
                # TODO: manage case where value is a PATH
                filepath='%s%s%s' % (currentPath, os.sep, properties.getProperty(key).strip())
                if not os.path.exists(filepath):
                    logger.error('loadOtherProperties() - include file "%s" does not exists' % (filepath))
                    raise SyntaxError('loadOtherProperties() - include file "%s" does not exists' % (filepath))
                try:
                    logger.trace('loadOtherProperties() - Loading %s' % (filepath))
                    newProps.load(FileInputStream(filepath))
                except Exception,e:
                    logger.error('loadOtherProperties(): exception raised, reason: %s' % (e))
                    raise e
        
        # Re-apply kept one
        for key in otherKeys.keys():
            newProps.setProperty(key,properties.getProperty(key))
                
        logger.trace('Final properties: "%s"' % (newProps))
        return newProps

bootstrapLibrairies()

