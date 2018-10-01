'''
Created on Oct 10, 2010

@author: omerlin
'''
import random
from threading import Condition
import unittest


cv_identifier= Condition()

class idGenerator:

    RANDOM_ARRAY=False
    # Class variable - allows to share memory
    identifier=[]

    def __init__(self, strArgs):
        '''
           a random list of unique id for Grindertool
           __init__ parameters:
               min
               max
               Number of concurrent thread (grinder.threads)
               use a randomized array? 0=No|1=Yes
               debug mode? 0=No|1=Yes
        '''
        digits=-1
        self.random_array=False
        self.debugVar=False
        params = [long(x) for x in strArgs.split(',')]
        if len(params)<3:
            raise SyntaxError("msisdnGenerator: Need 3 numbers (min, max, number of Threads [grinder.threads]) and 3 optional: random Array[0|1], N digits to align, Debug[0|1]) \nyou gave '%s'\n%s" % (strArgs, x))
        self.min=params[0] 
        self.max=params[1] 
        self.nb_threads=params[2]
        try:
            random_array= int(params[3]) == 1
            if random_array:
                self.__class__.RANDOM_ARRAY=True
        except:
            pass
        try:
            digits= params[4]
        except:
            pass
        try:
            self.debugVar = params[5] == 1
        except:
            pass
 
        self.debug('[min=%d][max=%d][nbThreads=%d][random=%s][digits=%d]' % (self.min,self.max,self.nb_threads,self.__class__.RANDOM_ARRAY,digits))        
        self.format = "%%0%dd" %digits if digits > 0 else '%d'
        self.counter=0

        if self.__class__.RANDOM_ARRAY:
            # We protect this call - only one initialization
            self.debug( 'BEFORE LOCK()' )
            cv_identifier.acquire()
            if not self.__class__.identifier:
                self.debug('Shuffling identifiers')
                self.__class__.identifier = range(self.min,self.max)
                random.shuffle(self.__class__.identifier)
                self.debug('Shuffling done, len=%d' % (len(self.__class__.identifier)))
            cv_identifier.release()
            self.debug( 'AFTER LOCK()' )

    def debug(self, message):
        if self.debugVar:
            print message

    def __repr__(self):
        return 'min=%d,max=%d,nbThreads=%d,random=%s' % (self.min,self.max,self.nbThread,self.__class__.RANDOM_ARRAY)
   
    def clear(self):
        self.__class__.identifier=[]
        self.__class__.RANDOM_ARRAY=False
        
    def popValue(self):
        value=''
        if self.__class__.RANDOM_ARRAY:
            try:
                value=self.format % self.__class__.identifier.pop()
            except:
                raise ValueError('No more value in the array')
        else:
            raise SyntaxError('You cannot use popValue() if you are not in random mode. Review your scenario')
        return value
        
    def getValue(self, params):
        '''
           Get a randomized msisdn
           parameter:
             params - a string with ',' delimiter
                 string[0]=>thread number (grinderThreadNumber)
                 string[1]=>run number (grinderRunNumber)
        '''
        try:
            (threadNumber,runNumber) = [long(x) for x in params.split(',')]
        except Exception, x:
            raise SyntaxError('msisdnGenerator: Need 2 numbers (ThreadNumber, runNumber) you gave "%s"\n%s'%
                              (params, x))
        ident=0
        if self.__class__.RANDOM_ARRAY:
            index = runNumber*self.nb_threads+threadNumber
            try:
                ident=self.__class__.identifier[index]
            except:
                raise ValueError('Error accessing data array (index=%d), you probably didn''t set the good thread number parameter in your scenario [use grinder.threads]'  % (index))
        else:
            ident=self.min+runNumber*self.nb_threads+threadNumber

        return self.format % (ident)

    def getName(self):
        return self.__class__.__name__


def initialize(strArgs):
    instance = idGenerator(strArgs)
    return instance

class Test(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    def title(self):
        s='Running : %s' % (self.id())
        print 
        print s
        print '='*len(s)
        
    def testWithoutRandom(self):
        self.title()
        nbThreads=32
        i1=initialize('3360409227,3360410227,%d,0,-1,1' % (nbThreads))
        for r in range(0,10):
            s=''
            for t in range(0,nbThreads):
                s+= '%s '% (i1.getValue('%d,%d' % (t,r)))
            print s
        i1.clear()

    def testRandom(self):
        self.title()
        nbThreads=32
        i1=initialize('3360409227,3360410227,%d,1,-1,1' % (nbThreads))
        for r in range(0,10):
            s=''
            for t in range(0,nbThreads):
                s+= '%s '% (i1.getValue('%d,%d' % (t,r)))
            print s
        i1.clear()

    def testRandomWithPadding(self):
        self.title()
        nbThreads=32
        i1=initialize('3360409227,3360410227,%d,1,12,1' % (nbThreads))
        for r in range(0,10):
            s=''
            for t in range(0,nbThreads):
                s+= '%s '% (i1.getValue('%d,%d' % (t,r)))
            print s
        i1.clear()



if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)
    