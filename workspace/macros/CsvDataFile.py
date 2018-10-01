'''
  a generic macro to load testdata from a file
  Please note that interface conventions are required by grindertool.
'''
import random
import java
from csv import DictReader 

from java.util.concurrent.atomic import AtomicInteger
from corelibs.coreGrinder  import CoreGrinder
logger=CoreGrinder.getLogger()

class CsvDataFile:
    '''
    Access to the class name are only done through the factory function.
    '''
    
    testdata=[]
    count=0
    index=AtomicInteger(0)
    
    def __init__(self, filename):
        ''' 
        Constructor. only called through the interface
        eventualy expensive initializations should be done here.
        You should carefully parse strArgs, and raise propper exceptions with descriptive messages.
        :Parameters:
          - `strArgs` contains the string from inbetween the template parentheses
              We expect it to contain a filename; each line of the File is becomming one test item
        '''
        logger.info('CSVDataFile: Using filename: %s' % (filename))
        try:
            fp = open(filename, 'r')
        except Exception, e:
            logger.error('FAILED ! reason %s' % (e))
            raise SyntaxError("TestDataFile initialisation failed, something went wrong with the file you specified. %s\n %s" 
                              %(filename, e))
        try: 
            datafile = DictReader(fp, delimiter=';')
            for line in datafile:
                self.testdata.append(line)
            fp.close()
        except Exception, x:
            raise SyntaxError("TestDataFile initialisation DictReader failed, something went wrong with the file you specified. %s \n %s" 
                              %(filename, x))
        self.count = len(self.testdata)
        if self.count < 1:
            raise SyntaxError("TestDataFile the file you specified was empty. %s" 
                              %(filename))

    def __repr__(self):
        return __name__
    
    def getValue(self, strArgs ):
        ''' 
        Runtime Macro Call. This is the function you call from the Template to get the values for parameterization.
        You can have more than one per Object.
        You should carefully parse strArgs, and raise propper exceptions with descriptive messages.
        :Parameters:
          - `strArgs` contains the string from inbetween the template parentheses
              We expect it to contain a number; we will use it to address the line of the file.
        :Returns:
           line from file to return.
        '''
        LineNR = int(strArgs)
        if (LineNR < 0):
            LineNR = 0;
        
        return self.testdata[LineNR % self.count]

    def nextValue(self):
        return self.testdata[self.index.getAndIncrement() % self.count]

    def getRandomValue(self, MTString):
        ''' 
        Runtime Macro Call. This is the function you call from the Template to get the values for parameterization.
        You can have more than one per Object.
        You should carefully parse strArgs, and raise propper exceptions with descriptive messages.
        :Parameters:
          - `MTString` not used.
        :Returns:
           random line from file to return.
        '''
        return random.choice(self.testdata)
        
    def getName(self):
        return self.__class__.__name__
    
def initialize(strArgs):
    '''
    initialize is the factory for this macro. It should return an instance of the TestData class
    note that you have to obey the interface.
    :Parameters:
      - `strArgs`: contains the string from inbetween the template parentheses
    :Returns: Instance of TestMacro1 for later use.
    '''
    instance = CsvDataFile(strArgs)
    return instance

if __name__ == '__main__':
    print "Cannot be used as a standalone program"