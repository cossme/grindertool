'''
Created on 25 oct. 2014

@author: omerlin
'''
import os
from corelibs.filetoolbox import checkProperty,checkPropertyList
from corelibs.scenario import ScenarioFile
#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
from net.grinder.script.Grinder import grinder

from itertools import chain
import fnmatch

def expand_list(dirname, fileIn):
    """
       Expand star ('*') in the filein list of files
    :param dirname: dataFilePath property content
    :param fileIn: the list of files to test separated by comma
    """

    def expand_token(token):
        if any(map(lambda c: c in token, ['*', '?', '['])):
            # Glob
            return filter(lambda f: fnmatch.fnmatch(f, token) and not os.path.isdir(os.path.join(dirname, f)),
                          os.listdir(dirname))
        else:
            # Filename
            return [token]
         
    # Flatmap equivalent
    # warning: using chain instead of from iterable for jython 2.5.3 compatibility
    return chain (*map(expand_token,fileIn.split(",")))


class ScenarioList:
    def __init__(self, configuration_class):
        
        self.scenarioHash={}
        self.sumAsyncStep=0
        self.asyncTimeout=-1
        self.isAsynchronous=False
        self.use_contextManager=False
        
        self.oneFileByThread =configuration_class.oneFileByThread
        self.oneFileByProcess=configuration_class.oneFileByProcess
        self.oneSingleList= not (self.oneFileByProcess or self.oneFileByThread)
        self.dataFilePath=configuration_class.dataFilePath
        self.numberOfProcess=configuration_class.numberOfProcess
        self.processNumber=configuration_class.processNumber
        
        # One single scenario list
        if self.oneSingleList:
            self.__initScenarioList()
        # Validation mode - can work only if flows are synchronous
        elif self.oneFileByThread:
            self.__initScenarioPerThread()            
        # Performance mode & validation mode when flows may be asynchronous
        elif self.oneFileByProcess:
            self.__initScenarioPerProcess()

    def getFirstScenario(self):
      
        if self.oneSingleList or self.oneFileByProcess:
            return self.scenarioHash[0]
        elif self.oneFileByThread:
            return self.scenarioHash[grinder.threadNumber][0]
            
    def getLastScenario(self):
        '''
          get the last available scenario in the ordered list
        '''
        if self.oneSingleList or self.oneFileByProcess:
            return self.scenarioHash[-1]        
        elif self.oneFileByThread:
            return self.scenarioHash[grinder.threadNumber][-1]

    def getScenario(self, index):
        if self.oneSingleList or self.oneFileByProcess:
            return self.scenarioHash[index]        
        elif self.oneFileByThread:
            return self.scenarioHash[grinder.threadNumber][index]

    def getAsyncStepsCount(self):
        return self.sumAsyncStep

    def getAsyncTimeout(self):
        return self.asyncTimeout
    
    def isAsync(self):
        return self.isAsynchronous
    
    def isUsingContextManager(self):
        return self.use_contextManager
    
    def setUseContextManager(self):
        self.use_contextManager=True
   
    def setAsync(self):
        self.isAsynchronous=True
    
    def getList(self):
        '''
           Return the scenario list depending of the execution context 
             - only one list of scenario
             - a list of scenario per thread
             - a list of scenario per worker process 
        '''
        if self.oneSingleList or self.oneFileByProcess:
            return self.scenarioHash
        elif self.oneFileByThread:
            return self.scenarioHash[ grinder.threadNumber ]
        else:
            raise SyntaxError("Bad configuration of your scenario, please check")
            return None

    def __caseAsyncScenario(self, scenarioFile):
        if scenarioFile.isAsynchronous():
            if not self.isAsync():
                self.setAsync()
            if scenarioFile.use_contextManager:
                if not self.isUsingContextManager():
                    self.setUseContextManager()
            self.sumAsyncStep+=scenarioFile.getAsyncStepsCount()
            self.asyncTimeout=max(self.asyncTimeout,scenarioFile.getAsyncTimeout())


    def __initScenarioList(self):
        scenarioList=[]
        fileInSetting = checkProperty('filein')
        if not fileInSetting:
            logger.error('Mandatory Property "filein" not defined')
            raise SyntaxError('Mandatory Property "filein" not defined')
        
        # Tearup / teardown for validation
        fileInTearUp= checkPropertyList( ['filein.tearup','filein.before','scenarioBefore'] )  
        if fileInTearUp:
            fileInSetting='%s,%s' % (fileInTearUp, fileInSetting)
        fileInTearDown= checkPropertyList( ['filein.teardown','filein.after','scenarioAfter'] )  
        if fileInTearDown:
            fileInSetting='%s,%s' % (fileInSetting, fileInTearDown)
            
        logger.debug('## scenarioList ## Scenario:  [filein=%s]' % ( fileInSetting))
        for scenarioId, scenario  in enumerate(expand_list(self.dataFilePath,fileInSetting)):            
            fullscenario='%s%s%s' % (self.dataFilePath, os.sep, scenario)
            logger.debug('\t>>Fullscenario=%s, current path=%s' % (fullscenario, os.getcwd()))
            if os.path.exists(fullscenario):
                scenarioFile=ScenarioFile(self.dataFilePath, scenario, scenarioId)
                scenarioList.append(scenarioFile)
                self.__caseAsyncScenario(scenarioFile)
                logger.debug('\t>>ScenarioFile appended to scenarioList List=%s' % (str(scenarioList)))
            else:
                logger.error('Scenario File %s listed in filein property not found - current=%s' % (fullscenario,os.getcwd()))
                raise IOError('Scenario File %s listed in filein property not found - current=%s' % (fullscenario,os.getcwd()))
        self.scenarioHash = scenarioList
        if logger.isTraceEnabled():
            logger.trace('ScenarioHash = %s, type=%s, asynchronous=%s' % (str(self.scenarioHash), type(self.scenarioHash),scenarioFile.isAsynchronous()))
            for j in  self.scenarioHash:
                logger.trace('type=%s scenario=%s' % (type(j), str(j)))

    
    def __initScenarioPerThread(self):
        scenarioList=[]
        for k in range(self.numberOfThreads):
            scenarioFile=None
            filename='filein%d' % (k)
            fileInSetting=properties.get(filename) or None
            if fileInSetting:
                logger.debug('** oneFileByThread ** Scenario list: [Thread=%d] [%s=%s]' % (k, filename, properties.get(filename)))
                for scenarioId, scenario  in enumerate(expand_list(self.dataFilePath,fileInSetting)):            
                    scenarioFile = ScenarioFile(self.dataFilePath, scenario,scenarioId)
                    if not scenarioFile:
                        logger.error('File %s not found, while mode **oneFilePerThread** is activated and number of threads defined is %d' % (filename, self.numberOfThreads))
                        raise SyntaxError('File %s not found, while mode **oneFilePerThread** is activated and number of threads defined is %d' % (filename, self.numberOfThreads))
            else:
                logger.error('Key %s not found required when using **oneFilePerThread** mode' % (filename))
                raise SyntaxError('Key %s not found required when using **oneFilePerThread** mode' % (filename))
            scenarioList.append(scenarioFile)
            self.__caseAsyncScenario(scenarioFile)
            self.scenarioHash[k] = scenarioList

    def __initScenarioPerProcess(self):
        logger.trace('__initScenarioPerProcess numberOfProcess is %s' % (self.numberOfProcess))
        scenarioList=[]
        # Method based on the fileinX where X is a number
        scenarioFile=None
        fileInSetting=checkProperty('filein%d' % (self.processNumber))
        if fileInSetting:
            logger.debug('** oneFileByProcess ** Scenario list: [Process=%d] [%s=%s]' % (self.processNumber, 'filein%d' % (self.processNumber),fileInSetting))
            for scenarioId, scenario  in enumerate(expand_list(self.dataFilePath,fileInSetting)):            
                scenarioFile = ScenarioFile(self.dataFilePath, scenario,scenarioId)
                scenarioList.append(scenarioFile)
                self.__caseAsyncScenario(scenarioFile)
        else:
            fileInSetting = checkProperty('filein')
            if fileInSetting:
                for scenarioId, scenario  in enumerate(expand_list(self.dataFilePath,fileInSetting)):            
                    try:
                        scenarioFile = ScenarioFile(self.dataFilePath, '%s%d' % (scenario,self.processNumber),scenarioId)
                    except:
                        pass
                    if not scenarioFile:
                        try:
                            scenarioFile = ScenarioFile(self.dataFilePath, '%s.in.%d.yaml' % (scenario.split('in')[0],self.processNumber),scenarioId)
                        except:
                            pass
                        if not scenarioFile:
                            scenarioFile = ScenarioFile(self.dataFilePath, '%s.in.%d.yml' % (scenario.split('.in')[0],self.processNumber),scenarioId)     
                        scenarioList.append(scenarioFile)
                        self.__caseAsyncScenario(scenarioFile)
            else:
                logger.error('Required parameters for **oneFileProcess** mode "filein" is not defined ?' )
                raise SyntaxError('Required parameters for **oneFileProcess** mode "filein" is not defined ?')

        if not scenarioList:                
            logger.error('fileinX property (X=Numero of process) [NumProcess=%d] not defined despite you are in **oneFileProcess** mode' % (self.processNumber))
            raise SyntaxError('fileinX property (X=Numero of process) [NumProcess=%d] not defined despite you are in **oneFileProcess** mode' % (self.processNumber))
        
        
        self.scenarioHash = scenarioList
        logger.trace('** oneFileByProcess ** Scenario list: [Process=%d] %s' % (self.processNumber, self.scenarioHash))


    def __initScenarioPerProcessOrig(self):
        scenarioList=[]
        # Method based on the fileinX where X is a number
        for k in range(self.numberOfProcess):
            scenarioFile=None
            filename='filein%d' % (k)
            if properties.get(filename):
                logger.debug('** oneFileByProcess ** Scenario list: [Process=%d] [%s=%s]' % (k, filename, properties.get(filename)))
                for scenarioId, scenario  in enumerate(filename.split(',')):
                    scenarioFile = ScenarioFile(self.dataFilePath, scenario,scenarioId)
                    scenarioList.append(scenarioFile)
                    self.__caseAsyncScenario(scenarioFile)
            else:
                fileInSetting = checkProperty('filein')
                if fileInSetting:
                    for scenarioId, scenario in enumerate(fileInSetting.split(',')):
                        scenarioFile = ScenarioFile(self.dataFilePath, '%s%d' % (fileInSetting,k),scenarioId)
                        if not scenarioFile:
                            scenarioFile = ScenarioFile(self.dataFilePath, '%s.in.%d.yaml' % (fileInSetting.split('.in')[0],k),scenarioId)
                            if not scenarioFile:
                                scenarioFile = ScenarioFile(self.dataFilePath, '%s.in.%d.yml' % (fileInSetting.split('.in')[0],k),scenarioId)                            
                            scenarioList.append(scenarioFile)
                            self.__caseAsyncScenario(scenarioFile)
                else:
                    logger.error('Required parameters for **oneFileProcess** mode : %s or %s are not defined' % (filename, fileInSetting))
                    raise SyntaxError('Required parameters for **oneFileProcess** mode : %s or %s are not defined' % (filename, fileInSetting))
                    
