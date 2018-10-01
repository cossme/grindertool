'''
Created on Oct 10, 2010

@author: omerlin
'''
from __future__ import with_statement
import random
from threading import Condition
import unittest
from corelibs.coreGrinder  import CoreGrinder


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()


cv_identifier= Condition()

class identifierGenerator:

    RANDOM_ARRAY=False
    minValue=0
    amount=0
    debugActivated=False
    zerodigits=17
    nbThreads=properties.getInt('grinder.threads', -1) 
    cycling=False
    current=0
    
    # Class variable - allows to share memory
    identifier=[]

    @classmethod
    def manageParameters(cls, strArgs):

        cls.identifier=[]

        args=None
        try:
            args=dict(k.split('=') for k in strArgs.split(';'))
        except Exception:
            logger.error('Incorrect parameter String format. Delimiter are ";" , name,value separated by "="')
            raise SyntaxError('Incorrect parameter String format. Delimiter are ";" , name,value separated by "="')
        
        try:
            cls.minValue = int(args['min']) if 'min' in args else 0
            cls.current=cls.minValue
        except Exception:
            raise ValueError('Incorrect value entered for parameter "min". Should be an int() value')

        # random ?
        cls.cycling='cycle' in args and args['cycle'].lower() in ('true','t','y','yes')

        try:
            if 'amount' in args:
                cls.amount = int(args['amount'])
            else:
                if cls.cycling:
                    raise SyntaxError('"amount" parameter is mangatory when cycling is set to True')
        except Exception:
            raise ValueError('Incorrect value entered on "amount" (value=%s ) parameter ! Should be an int()' % (args['amount']))
        
        # zero padding format
        if 'zerodigits' in args:
            try:
                cls.zerodigits = int(args['zerodigits']) if 'zerodigits' else 17
            except:
                raise ValueError('Incorrect value entered for parameter "zerodigits". Should be an int() value')
            
        # random ?
        cls.RANDOM_ARRAY='random' in args and args['random'].lower() in ('true','t','y','yes')

        # debug ?
        cls.debugActivated='debug' in args and args['debug'].lower() in ('true','t','y','yes')



        if cls.RANDOM_ARRAY and not cls.identifier:
            cls.debug('**** Shuffling ****')
            cls.shuffle()



    @classmethod
    def shuffle(cls):
        with cv_identifier:
            if not cls.identifier:
                cls.debug('Shuffling identifiers')
                cls.identifier = range(cls.minValue,cls.minValue+cls.amount)
                random.shuffle(cls.identifier)
                cls.debug('Shuffling done, len=%d' % (len(cls.identifier)))
                

    def __init__(self, strArgs):
        '''
           a random list of unique id for Grindertool
           __init__ parameters:
               min: Minimum value (default 0)
               amount: Number of identifier (Mandatory)
               zerodigits: padded to '0' digits (Optional - defaulted to 16). should call getValuePadded() to benefit from padding
               use a randomized array? 
               debug mode?
        '''
        self.__class__.manageParameters(strArgs)

         
    @classmethod
    def debug(cls, message):
        if cls.debugActivated:
            print message

    def __repr__(self):
        return 'min=%d,amount=%d,nbThreads=%d,random=%s' % (self.min,self.amount,self.nbThread,self.__class__.RANDOM_ARRAY)
    
    
    @classmethod
    def popValueFormatted(cls):
        return '%0*d' % (cls.zerodigits, cls.popValue())
    
    @classmethod
    def popValue(cls):
        if not cls.RANDOM_ARRAY:
            raise SyntaxError('You cannot use popValue() if you are not in random mode. Review your scenario')        
        try: 
            return cls.identifier.pop()
        except:
            raise ValueError('Macro "%s" - No more value in the array' % (cls.__name__))
    
    
    @classmethod
    def getNextValueFormatted(cls):
        with cv_identifier:
            cls.current+=1
            return '%0*d' % (cls.zerodigits, cls.minValue+(cls.current%cls.amount if cls.cycling else cls.current))
    
    @classmethod
    def getNextValue(cls):
        with cv_identifier:        
            cls.current+=1
            return cls.minValue+(cls.current%cls.amount if cls.cycling else cls.current)
        
    
    @classmethod
    def getValueFormatted(cls):
        return '%0*d' % (cls.zerodigits, cls.getValue())
    
    @classmethod
    def getValue(cls):
        '''
           Get an identifier located by it's threadNumber,runNumber position
        '''
        index = grinder.runNumber*cls.nbThreads+grinder.threadNumber
        if cls.RANDOM_ARRAY:
            try:
                return cls.identifier[index%cls.amount if cls.cycling else index ]
            except:
                raise ValueError('Error accessing data array (index=%d, amount=%d, modulo=%d), you probably didn''t set the good thread number parameter in your scenario [use grinder.threads]'  % (index, cls.amount, index%cls.amount))
        else:
            return cls.minValue + (index%cls.amount if cls.cycling else index)

    def getName(self):
        return self.__class__.__name__


def initialize(strArgs):
    instance = identifierGenerator(strArgs)
    return instance

#===============================================
#    TESTING PART
#===============================================
    


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
        
    def testWithRandom(self):
        self.title()
        
        identGenerator=initialize('min=3360409227;amount=1000;random=true;debug=true' )
        for _ in range(0,10):
            print '%d - %s ' % (identGenerator.popValue() , identGenerator.popValueFormatted())

    def NOtestNORandom(self):
        self.title()
        identGenerator=initialize('min=3360409227;amount=1000;random=false;debug=true' )
        for _ in range(0,10):
            print '%d - %s ' % (identGenerator.popValue() , identGenerator.popValueFormatted())

    def testRandomGetValue(self):
        self.title()
        identGenerator=initialize('min=3360409227;amount=10000;random=true;debug=true;cycle=True' )
        for _ in range(0,10):
            grinder.threadNumber+=_
            print '%d - %s ' % (identGenerator.getValue() , identGenerator.getValueFormatted())


    def testNextValue(self):
        self.title()
        identGenerator=initialize('min=3360409227;amount=10;random=true;debug=true;cycle=true' )
        for _ in range(0,20):
            print '%d - %s ' % (identGenerator.getNextValue() , identGenerator.getNextValueFormatted())

        identGenerator=initialize('amount=10;random=true;debug=true;cycle=true' )
        for _ in range(0,20):
            print '%d - %s ' % (identGenerator.getNextValue() , identGenerator.getNextValueFormatted())



    def NotestRandomWithPadding(self):
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
    