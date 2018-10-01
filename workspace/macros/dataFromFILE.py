from __future__ import with_statement
import os
from itertools import imap
import random
from threading import Condition
import time
import unittest

from corelibs.coreGrinder  import CoreGrinder


properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()


class FakeGrinder(object):
    def __init__(self, maxLines, nbThreads):
        self.runNumber=random.randint(0,maxLines)
        self.threadNumber=random.randint(0,nbThreads)

class dataFromFILE(object):
    '''
          A simple CSV file loader for grindertool
    '''
    
    rows=[]
    mutex=Condition()
    mutex_optional=Condition()
    
    maxThreads=0
    maxSize=0
    maxGrinderIndex=0
    nbColumns=0
    format=None
    formatUsage=False
    current_row=0
    cycling=False
    optionalCounter=None
    filename=''

    @classmethod
    def reset(cls):
        cls.rows=None
    
    @classmethod
    def loadFile(cls, strArgs):
        '''
           Load the whole CSV file as fixed columns tuple
           the file could have already zero padded values Or the padding is done when returning data
           This could be useful to reduce the file size and the memory consumption
            
        :param cls:
        :param strArgs:
        '''        
        if not cls.rows:
            with cls.mutex:
                if not cls.rows:
                    cls.manageParameters(strArgs)
                    
                    cls.rows=[ tuple(k[:-1].split(';')) for k in open(cls.filename).readlines()]
                    cls.maxSize=len(cls.rows)
                    if cls.maxSize<cls.maxGrinderIndex and not cls.cycling:
                        raise SyntaxError('Your number of lines in the file (%s) SHALL be at least greater than the number of test (%d)' % (cls.maxSize,cls.maxGrinderIndex) )
                    cls.nbColumns=len(cls.rows[0])
                    if cls.formatUsage:
                        if len(cls.format) != cls.nbColumns:
                            raise SyntaxError('When using tuple format string, the number of format columns (%d) must be equal to the number of file columns (%d)' % (len(cls.format), cls.nbColumns))
     


    @classmethod
    def manageParameters(cls, strArgs):
        args=None
        try:
            args=dict(k.split('=') for k in strArgs.split(';'))
        except Exception:
            logger.error('Incorrect parameter String format. Delimiter are ";", name,value separated by "="')
            raise SyntaxError('Incorrect parameter String format. Delimiter are ";", name,value separated by "="')
        # File parameter
        if 'file' not in args :
            logger.error('Required parameter "file" is absent')
            raise SyntaxError('Required parameter "file" is absent')
        
        cls.filename=args['file']
        if not os.path.exists(args['file']):
            logger.error('File %s does not exists ! ' % (args['file']))
            raise SyntaxError('File %s does not exists ! ' % (args['file']))
        del args['file']
        
        # column format
        if 'format' in args:
            cls.format=eval(args['format'])
            if not isinstance(cls.format,tuple):
                logger.error('column format must be a list of numeric values separated by "," delimiter')
                raise SyntaxError('column format must be a list of numeric values separated by "," delimiter')
            cls.formatUsage=True
            del args['format']
        
        # Cycling on data file ?
        cls.cycling='cycle' in args and args['cycle'].lower()=='true'
        if 'cycle' in args:
            del args['cycle']
        
        # (Optional) Parameters that are increasing when cycling
        if args:
            logger.debug('Optional args=%s' % (str(args)))
            cls.optionalCounter=dict(args)
            # check values
            try:
                for key,value in cls.optionalCounter.iteritems():
                    cls.optionalCounter[key]=int(value) 
            except:
                logger.error('Optional args must be int() values')
                raise SyntaxError('Optional args must be int() values')
            

        #=================================
        # Control the maximum througput
        #=================================                            
        profile=properties.get('throughput_rampup') or None
        if profile:
            try:
                # String : tps1,duration1 tps2,duration2 ... tpsN,durationN
                cls.maxGrinderIndex = int(reduce(lambda x,y: x+y, list(imap(lambda x: float(x.split(',')[0])* float(x.split(',')[1]) , profile.split()))))
                
                # target
                target=properties.getInt('throughput_target', 0)
                if target:
                    cls.maxGrinderIndex = target
                
            except:
                logger.error('Incorrect throughput_rampup string: "%s" ' % (profile))
                raise SyntaxError('Incorrect throughput_rampup string: "%s" ' % (profile))
        else:
            cls.maxThreads=int(properties.get('grinder.threads')) 
            maxRuns=int(properties.get('grinder.runs'))
            if not maxRuns:
                maxRuns=9999 
            cls.maxGrinderIndex=maxRuns*cls.maxThreads
                

        
    def __init__(self, strArgs):
        '''
           TODO : documentation
           :param strArgs: a string parameter 
        '''      
        # Load the file
        self.__class__.loadFile(strArgs)
    
    
    @classmethod
    def getCyclingValue(cls,strArgs):
        '''
           optionalCounter are counters incremented only when cycling at the end of data volume (cls.cycling=True) 
        :param cls: the class
        :param strArgs: format "counterName,zerodigits" 
                       where counterName : is a counter that was passed to the init string ( example: sequenceId )
                             zerodigits  : left zero padding size
        '''
        key=strArgs
        if strArgs.find(',')>=0:
            key,len0=strArgs.split(',')
        with cls.mutex_optional:
            return '%0*d' % (int(len0), cls.optionalCounter[key])
    
    
    
    @classmethod
    def getNextElem(cls, index):
        '''
           Read in a serialized way the file. 
           getElem uses the (run, thread) couple to get an element from the class list rows.   
           :param index: the column index
        '''
        index=int(index)
        with cls.mutex:
            cls.current_row+=1
            if  cls.current_row>cls.maxSize:
                if cls.cycling:
                    cls.current_row=1
                    for k in cls.optionalCounter:
                        cls.optionalCounter[k]+=1
                else:
                    errMsg='[thread=%d][run=%d][nbThreads=%d] index %d is over maximum file size %s' % (grinder.threadNumber,grinder.runNumber,
                                                                       cls.maxThreads, cls.current_row, cls.maxSize)
                    logger.error(errMsg)
                    raise IndexError(errMsg)
            return '%0*d' % (cls.format[index],cls.rows[cls.current_row-1][index]) if cls.formatUsage else cls.rows[cls.current_row-1][index]
    
    @classmethod    
    def getElem(cls, index):
        '''
           Get one element in the in-memory list using grinder (grinder.threadNumber, grinder.runNumber) 
           :param index: the file column index beginning at index 0
        '''
        k = (grinder.threadNumber+grinder.runNumber*cls.maxThreads) % (cls.maxSize) if cls.cycling else grinder.threadNumber+grinder.runNumber*cls.maxThreads
        if k>cls.maxSize:
            errorMsg='[thread=%d][run=%d][nbThreads=%d] index k=%d is over maximum file size %s' % (grinder.threadNumber,grinder.runNumber,cls.maxThreads, k, cls.maxSize)
            logger.error(errorMsg)
            raise IndexError(errorMsg)
        try:
            return '%0*d' % (cls.format[index],int(cls.rows[k][index])) if cls.formatUsage else cls.rows[k][int(index)]
        except Exception:
            if index>(cls.nbColumns-1):
                raise SyntaxError('index=%d is bigger than the number of columns in the file' % (index))
            raise
        return '0'
        
        
        
    def __repr__(self):
        return __name__

    def getName(self):
        return self.__class__.__name__


def initialize(strArgs):
    '''    
    '''
    instance = dataFromFILE(strArgs)
    return instance

class Test(unittest.TestCase):
    filename='c:/temp/msisdn_iccids.txt'
    nbThreads=1024
    nbRuns=100
    data=None

    def generate(self, filename, format):
        fout=open(filename,'w')
        size=self.nbThreads*self.nbRuns
        t0=time.time()
        for k in xrange(size):
            fout.write(format % (k,k))
        fout.close()
        print 'Generated file with %d entries in %f seconds' % (size, time.time()-t0)
        
 
    def load(self, strArgs):
        t0=time.time()
        self.data=dataFromFILE(strArgs)
        print '%f seconds - File loaded in memory' % (time.time()-t0)

    
    def setUp(self):
        
        properties.setProperty('grinder.threads',str(self.nbThreads))
        properties.setProperty('grinder.runs', str(self.nbRuns))
        
            
    def testFileFormatted(self):
        dataFromFILE.reset()
        self.generate('c:/temp/msisdn_iccids.txt', '%012d;%08d\n')
               
        data = initialize('c:/temp/msisdn_iccids.txt')
        
        global grinder
        for _ in xrange(10):
            grinder=FakeGrinder(self.nbRuns,self.nbThreads)
            t0=time.time()
            print '%f seconds - [run=%d,thread=%d] (%d) => (%s,%s)' % (time.time()-t0, grinder.runNumber, grinder.threadNumber, grinder.runNumber * grinder.threadNumber, data.getElem(0), data.getElem(1))

    def NotestRawFile(self):
        dataFromFILE.reset()
        self.generate('c:/temp/msisdn_iccids.txt', '%d;%d\n')
        data = initialize('c:/temp/msisdn_iccids.txt')
        global grinder
        for _ in xrange(10):
            grinder=FakeGrinder(self.nbRuns,self.nbThreads)
            t0=time.time()
            print '%f seconds - [run=%d,thread=%d] (%d) => (%s,%s)' % (time.time()-t0, grinder.runNumber, grinder.threadNumber, grinder.runNumber * grinder.threadNumber, data.getElem(0), data.getElem(1))

    def NotestRawFileFormatted(self):
        dataFromFILE.reset()
        self.generate('c:/temp/msisdn_iccids.txt', '%d;%d\n')
        data = initialize('c:/temp/msisdn_iccids.txt,(12,8)')

        global grinder
        for _ in xrange(10):
            grinder=FakeGrinder(self.nbRuns,self.nbThreads)
            t0=time.time()
            print '%f seconds - [run=%d,thread=%d] (%d) => (%s,%s)' % (time.time()-t0, grinder.runNumber, grinder.threadNumber, grinder.runNumber * grinder.threadNumber, data.getElem(0), data.getElem(1))


    def NotestLimit(self):
        dataFromFILE.reset()
        self.generate('c:/temp/msisdn_iccids.txt', '%d;%d\n')
        data = initialize('c:/temp/msisdn_iccids.txt,(12,8)')
        global grinder
        grinder=FakeGrinder(self.nbRuns,self.nbThreads)
        grinder.threadNumber=10
        grinder.runNumber=10200
        print '[run=%d,thread=%d] (index=%d/file size=%d/Nb tests=%d) => (%s,%s)' % (grinder.runNumber, grinder.threadNumber, grinder.runNumber *self.nbThreads+ grinder.threadNumber, data.maxSize, data.maxGrinderIndex,
                                                            data.getElem(0), data.getElem(1))
        

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)
