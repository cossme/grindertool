from __future__ import with_statement

from itertools import islice, imap
import os
import random
from threading import Condition
import time
import unittest

from corelibs.coreGrinder  import CoreGrinder

# USAGE EXAMPLE
# =================
# - macros:
#     - dataGen=dataChunkFromFILE.initialize(file=${file_location}/test.txt${PROCESS})
# - scenario:
#     name: SC1_creation_Activation
#     context:
#         data: dataGen.getLine()
#         iccid: dataGen.getdataElem(${data},0)
#         msisdn: dataGen.getdataElem(${data},1)
#         imsiVerizon: dataGen.getdataElem(${data},2)
# ==============================================================================
# "data" variable is necessary to copy the whole line
# then access each element with data.getdataElem(${data}, index)
#

#------------------------------------------
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()
# debug=True


#-------------------------------------------------------------
# Efficient way to count number of text lines
# without consuming too much memory
#-------------------------------------------------------------
def _make_gen(reader):
    b = reader(1024 * 1024)
    while b:
        yield b
        b = reader(1024*1024)
 
def rawgencount(filename):
    f = open(filename, 'rb')
    f_gen = _make_gen(f.read)
    return sum( buf.count( '\n') for buf in f_gen )
#--------------------------------------------------------------


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
    initialized=False
    chunkIndex=0
    chunkGenerator=None
    filename=None
    cycling=False
    chunkSize=10000
    optionalCounter=None
    startFrom=0
            
    @classmethod
    def getNextChunkFromFile(cls):
        '''
           a generator of chunk of lines for big files
        :param cls:
        :param filename: the full path of the file
        :param chunkSize: the line chunk size 
        '''
        with open(cls.filename) as fd:
            # ignore the N (startFrom) first lines 
            if cls.startFrom:
                for _ in xrange(cls.startFrom):
                    fd.next()
            while True:
                nextLines = list(islice(fd, cls.chunkSize))
                if not nextLines:
                    break
                cls.chunkIndex+=1
                # Trick to reverse a list like a stack()
                yield nextLines[::-1]
        yield None
      
      
    @classmethod
    def getNextRowFromChunk(cls):
        '''
            Conservative version 
            :param cls:
        '''
        with cls.mutex:
            try:
                return cls.rows.pop()
            except (IndexError,AttributeError):
                cls.rows=cls.chunkGenerator.next()
                try:
                    return None if not cls.rows else cls.rows.pop()
                except Exception,e:
                    logger.error('getNextRowFromChunk() - STRANGE - failed with exception %s' % (str(e)))
                    raise e
            except Exception,e:
                logger.error('getNextRowFromChunk() - failed with exception %s' % (str(e)))
                raise e                    
                
            
    @classmethod
    def reset(cls):
        cls.rows=None

    @classmethod
    def manageArgs(cls, strArgs):
        args=dict([k.split('=') for k in strArgs.split(';')])
        if 'file' in args:
            cls.filename=args['file']
            if not os.path.exists(args['file']):
                logger.error('File %s does not exists ! ' % (args['file']))
                raise SyntaxError('File %s does not exists ! ' % (args['file']))
            del args['file']

        else:
            raise SyntaxError('"file" parameter is mandatory when using %s' % (cls.__name__))
        
        # Second param (optional): chunk size
        if 'chunk' in args:
            cls.chunkSize=int(args['chunk'])
            del args['chunk']
        
        # format is a tupple "(9,10)" for example
        if 'format' in args:
            try:
                cls.format=eval(args['format'])
                del args['format']
            except:
                raise SyntaxError('Invalid number format. Should be a list of decimal format separated by comma or semi-comma')

        # Cycling on data file ?
        cls.cycling='rotate' in args and args['rotate'].lower()=='true'
        if 'rotate' in args:
            del args['rotate']
        
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
                                


    @classmethod
    def checkArgs(cls):
        '''
              Control the maximum throughput
              MUST BE REWRITTEN !!! This don't take into account PERCENTAGE management !!!
        :param cls:
        '''
        profile=properties.get('throughput_rampup') or None
        if not profile:
            cls.maxThreads=int(properties.get('grinder.threads')) 
            cls.maxRuns=int(properties.get('grinder.runs'))
            
            if not cls.maxRuns:
                raise SyntaxError('You cannot set grinder.runs=0 for a thread mode test (no throughput definition) !!')
            cls.maxGrinderIndex=cls.maxRuns*cls.maxThreads
        else:                    
            try:
                # String : tps1,duration1 tps2,duration2 ... tpsN,durationN
                cls.maxGrinderIndex = int(reduce(lambda x,y: x+y, list(imap(lambda x: float(x.split(',')[0])* float(x.split(',')[1]) , profile.split()))))
                
                # target property
                cls.maxGrinderIndex = properties.getInt('throughput_target', 0) or cls.maxGrinderIndex
                
                # target_start_index : to ignore cards already processed
            
            except:
                logger.error('Incorrect throughput_rampup string: "%s" ' % (profile))
                raise SyntaxError('Incorrect throughput_rampup string: "%s" ' % (profile))

        # Here we check that the number of lines in the file is consistent
        fileSize=rawgencount(cls.filename)
        
        if cls.maxGrinderIndex>fileSize:
            raise SyntaxError('The file "%s" has a number of lines (%d) inferior to the testing runs (%d) ! use throughput_target to limit' % (cls.filename, fileSize, cls.maxGrinderIndex))
        


    @classmethod
    def initClass(cls, strArgs):
        
        cls.manageArgs(strArgs)
                            
        #========================
        # TEMPORY PUT IN COMMENTS
        # cls.checkArgs()
        #========================
        
        # to bypass (seek) N lines of the file
        cls.startFrom = properties.getInt('throughput_start_from%d' % (CoreGrinder.getRealProcessNumber()),0)
        if cls.startFrom:
            logger.info('We will ignore the first %d lines' % (cls.startFrom))
        
        # The chunkGenerator will allow to minimize memory usage
        cls.chunkGenerator = cls.getNextChunkFromFile()
        cls.rows=cls.chunkGenerator.next()
        
    def __init__(self, strArgs):
        '''
           This string has the format "filename,chunksize,format"
           where :
              filename (mandatory) is the full path to a list of CSV delimited data
            :param strArgs: a string parameter 
        '''  
        if not self.__class__.initialized:      
            with self.__class__.mutex:
                if not self.__class__.initialized:
                    self.__class__.initClass(strArgs)
                    self.__class__.initialized=True

    

    def getdataElem(self, strArgs):
        '''
          Return one element from splited line based on the index
        :param line:
        '''
        try:
            datas,index = strArgs.split(",")
            return datas.split(';')[int(index)]
        except Exception,e:
            logger.error('getElem: [strArgs=%s] other error raised: %s' % (strArgs, str(e)))
            raise 


    @classmethod
    def getAllElem(cls):
        return cls.getLine()

    @classmethod
    def getLine(cls):
        '''
           *** KEPT FOR COMPATIBILITY *** use getNextElem() instead
           Get one element in the in-memory list. 
           If outbound range, the row is a modulo on the max in-memory list size.
           :param index: the file column index beginning at index 0
        '''
        try:
            return cls.getNextRowFromChunk().strip()             
        except AttributeError:
            if cls.cycling:
                logger.debug( '='*10+' rotating '+'='*10)
                if cls.optionalCounter:
                    for k in cls.optionalCounter:
                        cls.optionalCounter[k]+=1
                with cls.mutex:
                    cls.chunkGenerator = cls.getNextChunkFromFile()
                return cls.getNextRowFromChunk().strip()
            logger.error('AttributeError - getElem(): EOF reached')
            raise EOFError('AttributeError - getElem(): EOF reached')
        except Exception,e:
            logger.error('getElem: other error raised: %s' % (str(e)))
            raise 
   
    
    
    @classmethod
    def getElem(cls, index=0):
        '''
           *** KEPT FOR COMPATIBILITY *** use getNextElem() instead
           Get one element in the in-memory list. 
           If outbound range, the row is a modulo on the max in-memory list size.
           :param index: the file column index beginning at index 0
        '''
        try:
            return cls.getNextRowFromChunk().strip().split(';')[int(index)]             
        except IndexError:
            if index>(cls.nbColumns-1):
                logger.error('index=%d is bigger than the number of columns in the file' % (index))
                raise SyntaxError('index=%d is bigger than the number of columns in the file' % (index))
        except AttributeError:
            if cls.cycling:
                logger.debug( '='*10+' rotating '+'='*10)
                if cls.optionalCounter:
                    for k in cls.optionalCounter:
                        cls.optionalCounter[k]+=1
                with cls.mutex:
                    cls.chunkGenerator = cls.getNextChunkFromFile()
                return cls.getNextRowFromChunk().strip().split(';')[int(index)]
            logger.error('AttributeError - getElem(): EOF reached')
            raise EOFError('AttributeError - getElem(): EOF reached')
        except Exception,e:
            logger.error('getElem: other error raised: %s' % (str(e)))
            raise 



    @classmethod
    def getNextFormattedElem(cls, index=0):
        return cls.getFormattedElem(index)
      
    @classmethod    
    def getFormattedElem(cls, index=0):
        '''
           Get one element in the in-memory list. 
           If outbound range, the row is a modulo on the max in-memory list size.
           :param index: the file column index beginning at index 0
        '''
        try:
            return '%0*d' % (cls.format[int(index)], cls.getElem(index))
        except Exception,e:
            logger.error('getFormattedElem: other error raised: %s' % (str(e)))
            raise 


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
    nbThreads=1024
    nbRuns=999

    def generateOfSize(self, filename, format, size):
        fout=open(filename,'w')
        t0=time.time()
        for k in xrange(size):
            fout.write(format % (k,k))
        fout.close()
        print 'Generated file with %d entries in %f seconds' % (size, time.time()-t0)

    
    def setUp(self):
         
#         properties.setProperty('grinder.threads',str(self.nbThreads))
#         properties.setProperty('grinder.runs', str(self.nbRuns))
        pass
            
            
    def NotestChunk(self):
        print '*****>>> testChunk() ....'
        self.generateOfSize('c:/temp/msisdn_iccids.txt', '%012d;%08d\n',10000001)
        dataGenerator=initialize('file=c:/temp/msisdn_iccids.txt;chunk=10000')
        i=0
        while True:
            row = dataGenerator.getNextRowFromChunk()
            if not row:
                print '=============> NO MORE ==================='
                break
            i+=1
            if not i%1000:
                print 'done - %d (chunk=%d)' % (i, dataFromFILE.chunkIndex)                    
                
        print 'Finished'
        
    def testGetElem(self):
        dataFromFILE.initialized=False
        properties.setProperty('grinder.threads',10)
        properties.setProperty('grinder.runs', 1)

        properties.setProperty('throughput_start_from',5)

        filetest='c:/temp/iccids_tmp.txt'
        self.generateOfSize(filetest, '%012d;%08d\n',23)
        dataGenerator=initialize('file=%s;chunk=5;rotate=true;sequenceId=23' % (filetest))
        
        for _ in range(5):
            for _ in range(10):
                col1=dataGenerator.getElem(0)
                col2=dataGenerator.getColumn(1)
                opt=dataGenerator.getCyclingValue('sequenceId,4')
                print ('col1=%s, col2=%s, opt=%s' % (col1, col2, opt))
      
    def testFile(self):
        dataFromFILE.initialized=False
        data='''86992000000001240000;869001240000;869001240000999
86992000000001240001;869001240001;869001240001999
86992000000001240002;869001240002;869001240002999
86992000000001240003;869001240003;869001240003999
86992000000001240004;869001240004;869001240004999
86992000000001240005;869001240005;869001240005999
86992000000001240006;869001240006;869001240006999
86992000000001240007;869001240007;869001240007999
86992000000001240008;869001240008;869001240008999
86992000000001240009;869001240009;869001240009999'''         
        filetest= 'c:/temp/testFile.txt'
        fd=open(filetest,'w')
        fd.write(data)
        fd.close()
        dataGenerator=initialize('file=%s;chunk=7;rotate=true' % (filetest))
        for _ in range(5):
            for _ in range(10):
                col1=dataGenerator.getElem(0)
                col2=dataGenerator.getColumn(1)
                col3=dataGenerator.getColumn(2)
                print ('col1=%s, col2=%s, col3=%s' % (col1, col2, col3))
        dataGenerator=None
        
if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)
