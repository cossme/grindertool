'''
Created on 23 sept. 2014

@author: omerlin
'''

#----------------------------------------------------------------------
from corelibs.coreGrinder import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------


class BaseConfiguration:
    '''
        This solve the issue with cycling initialization of class variable in Configuration
        So move variable here to avoid cycling dependencies error when invoking from Configuration method  
    '''
    IGNORE_TAGS='grindertool.step.tags.ignore'
    
    # step management
    ignoreOptionalSteps = properties.getBoolean('grindertool.steps.ignore', False)
    
    # Steps list to ignore
    tagsListToIgnore = properties.get(IGNORE_TAGS) or None

    # Redundancy  with Configuration.py   
    oneFileByProcess = properties.getBoolean('oneFileByProcess',  properties.getBoolean('grindertool.test.scenarioPerProcess', False))

    
    # To separate test number by a range when having different test in parallel in different    
    testRangeSize=properties.getInt('grindertool.test.range', 100)
