"""
Generic utils functions

Created August 02, 2009

"""
### this file is part of TheGrinderTool
from __future__ import with_statement

from __builtin__ import None
from contextlib import contextmanager


from java.util.regex import Pattern
import math
import sys
from time import gmtime, strftime
import time
import traceback

from corelibs.coreGrinder import CoreGrinder
properties=CoreGrinder.getProperties()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()

#
# grindertool object is loaded only at grindertool runtimer
# so the function based on grindertool.properties cannot be tested (or with grinderstone)
# - Avoid using it in libraries
# - or test the grindertool object existence (but the method, class, functions are not testable ...)
#
processNumberPadding=properties.getInt('processNumberPadding', 2)
threadNumberPadding=properties.getInt('threadNumberPadding', 4)
runNumberPadding=properties.getInt('runNumberPadding', 7)
idFormat='%%0%dd.%%0%dd.%%0%dd' %(processNumberPadding, threadNumberPadding, runNumberPadding)

# An Implementation's full Run ID includes the current line number treated. so it is made of :
#   . processNumberPadding + '.'
#   . threadNumberPadding + '.'
#   . runNumberPadding
#   . '.' + lineNumber
# Here, we get rid of the lineNumber and additional '.'
runIDPadding=processNumberPadding+1+threadNumberPadding+1+runNumberPadding



def writeToFile(fHandle, text):
    retVal = 0
    try:
        print >> fHandle, text
        retVal = len(text)
    except:
        pass
    
    return retVal
    
def popNewLine(listOfValues):
    """check if the last value in a list is a newline, cr-nl or nl, if so, remove that value
    returns the modified list"""
    if listOfValues[-1] == '\n' or listOfValues[-1] == '\r\n' or listOfValues[-1] == '\r':
        listOfValues.pop()

    return listOfValues

def stripNewLine(line):
    """remove the trailing NL from a line read by python
    returns a string"""
    line = line.rstrip()
    
    return line

def openAndReadFile(fileName):
    """ return content of the file as a string
        exception thrown on error
    """
    readStr = ''
    try:
        readStr = ''.join(open (fileName, 'r').readlines())
    except:
        exceptHandler('failure opening file')
    return readStr.strip()

def openBinaryFile(fileName):
    """ return content of the file as a binary string
        exception thrown on error
    """
    readStr = ''
    try:
        # JYTHON 2.5.1 - only 'r' - not 'ra'
        fIn = open (fileName, 'r')
        while 1:
            readLine = fIn.readline()     
            readStr += readLine
    except:
        exceptHandler('failure opening file')
    fIn.close()
    return readStr


def convert2Vars(str2use):
    """
    Optimized Java version
    conversion of an input string in format ${XX.string} to @VARXX where XX is 2 digits
    return the convert String"""
    replPattern = Pattern.compile('(\$\{(\d{1,2})\..+?})')
    match = replPattern.matcher(str2use)
    while(match.find()):
        replStr = '@VAR%02d' % int(match.group(2))
        str2use=str2use.replace(match.group(1),replStr) 
    
    return str2use


def parseLine(s,sep='|'):
    """split the string into a list, '|' is the default separator
    returns a list of fields."""
    return s.split(sep)

def exceptHandler(exceptStr):
    """print DETAILED stack traces when there are errors (there should be NONE)
    return nothing"""
    et, ev, etb = sys.exc_info()
    traceback.print_exception(et,ev,etb,file=sys.stdout)
    print exceptStr
    
def concurrentFileWrite(f,text,cv):
    """handling locking/concurrent write to the output file
    return nothing"""
    getattr(cv,'acquire')()
    writeToFile(f,text)
    getattr(cv,'release')()

def getTimeStamp():
    """create a timestring for output file logging, hoops necessary because milliseconds aren't directly available
    return the String"""
    timeVar = time.time()
    returnTime = strftime("%d/%m/%Y.%H:%M:%S", gmtime(timeVar))
    return '%s.%03d' % (returnTime,math.modf(timeVar)[0]*1000)

def getFileTimeStamp():
    """create a timestring for creating unique output filenames
    return the String"""
    timeVar = time.time()
    return '%s.%04d' % (strftime("%d.%m.%Y.%H.%M.%S", gmtime(timeVar)),math.modf(timeVar)[0]*1000)

def loadLBHostAndPort(moduleName):
    """ load the loadbalanced host/port number pairs for the module
       return the list of pairs"""

    # initialize the array
    liAddrPort = []
   
    # Don't be shy, go up to whopping 100 targets. :o)
    # range (1,101) will do items 1 thru 100
    for i in range(1,101):
        serverAddress = properties.get('%s_LB_host_%d' % (moduleName, i))
        serverPort = properties.get('%s_LB_port_%d' % (moduleName, i))

        # if the LoadBalance host or port was not found, searching is complete
        if serverAddress == None or serverPort == None:
            break

        liAddrPort.append(serverAddress)
        liAddrPort.append(serverPort)

    # if no rows were added, add the default host and port for the module
    if not liAddrPort:
        # added a default configuration
        _host=properties.get('%s_host' % (moduleName)) or 'localhost'
        _port=properties.get('%s_port' % (moduleName)) or 80
        liAddrPort.append(_host)
        liAddrPort.append(_port)
        if grinder.threadNumber == 0:
            logger.debug('loadLBHostAndPort(): protocol "%s" defaulted to "%s:%s"' % (moduleName,_host,_port ))

    return liAddrPort

def getLBHostAndPort(liAddrPort):
    """ determine the correct server IP address and port number, based upon the test_thread-number of the running test
       return that address and port"""
    return getLBHostAndPortWithID(liAddrPort, grinder.threadNumber)


# in order to be able to do some LB based on whatever id there is, 
# be it grindertool.runNumber or grindertool.threadNumber
# or anything else ( time of day, weather forecast ...
def getLBHostAndPortWithID(liAddrPort, a_value):
    """ determine the correct server IP address and port a_value, based upon the given a_value
     ( may be just about anything depending on implementation )
       return that address and port"""
    if a_value:
        #print("### DEBUG : given a_value for LB is [%s]" % (a_value))
        # retrieve the ID a_value, mod divide it with a_value of hosts
        nbAdresses = len(liAddrPort) / 2
        LB_Offset = (a_value % nbAdresses)    
        host = liAddrPort[LB_Offset*2]
        port = liAddrPort[(LB_Offset*2)+1]
    else:
        if liAddrPort:
            host,port = liAddrPort[0],liAddrPort[1]
        else:
            logger.error('FATAL : No host and port defined for the HTTP protocol !')
            raise
    # print '@@@@@ end getLB : ' + host + ':' + port + ' @@@@@'
    return host, port


def getLogon(processNumber):
    """retrieve a logon string from the properties file
       return the found string (or '' if not found)"""

    logonString = properties.get('mtas_logon_%d' % (processNumber))
    if logonString == None:
        logonString = ''

    return logonString

def getRunProcThreadNumPadding():
    # get the paddings -begin
    runNumberPadding = properties.get('runNumberPadding')
    if not runNumberPadding:
        runNumberPadding = 5
    else:
        # print 'runpad :' + runNumberPadding
        runNumberPadding = int(runNumberPadding)

    processNumberPadding = properties.get('processNumberPadding')
    if not processNumberPadding:
        processNumberPadding = 1
    else:
        # print 'propad :' + processNumberPadding
        processNumberPadding = int(processNumberPadding)

    threadNumberPadding = properties.get('threadNumberPadding')
    if not threadNumberPadding:
        threadNumberPadding = 2
    else:
        # print 'thrpad :' + threadNumberPadding
        threadNumberPadding = int(threadNumberPadding)

    # print '***'
    # print 'run : %d' % (runNumberPadding)
    # print 'pro : %d' % (processNumberPadding)
    # print 'thr : %d' % (threadNumberPadding)
    # print '***'

    # get the paddings - end    
    return runNumberPadding, processNumberPadding, threadNumberPadding

## {{{ http://code.activestate.com/recipes/510399/ (r1)
"""
HexByteConversion

Convert a byte string to it's hex representation for output or visa versa.

ByteToHex converts byte string "\xFF\xFE\x00\x01" to the string "FF FE 00 01"
HexToByte converts string "FF FE 00 01" to the byte string "\xFF\xFE\x00\x01"
"""

#-------------------------------------------------------------------------------
# from http://code.activestate.com/recipes/510399-byte-to-hex-and-hex-to-byte-string-conversion/ BEGIN
def ByteToHex( byteStr ):
    """
    Convert a byte string to it's hex string representation e.g. for output.
    """
    
    # Uses list comprehension which is a fractionally faster implementation than
    # the alternative, more readable, implementation below
    #   
    #    hex = []
    #    for aChar in byteStr:
    #        hex.append( "%02X " % ord( aChar ) )
    #
    #    return ''.join( hex ).strip()        

    return ''.join( [ "%02x" % ord( x ) for x in byteStr ] ).strip()

def ByteToHexforDigest( byteStr ):
    """
    Convert a byte string to it's hexTab string representation e.g. for output.
    """
    
    # Uses list comprehension which is a fractionally faster implementation than
    # the alternative, more readable, implementation below
    #   
    hexTab = []
    for aChar in byteStr:
        aInt = ord( aChar )
        ## remove trailing "FF"      
        if ( aInt > 128 ) : aInt = aInt - 65280
        hexTab.append( "%02x" % aInt )
    return ''.join( hexTab ).strip()        


#-------------------------------------------------------------------------------

def HexToByte( hexStr ):
    """
    Convert a string hex byte values into a byte string. The Hex Byte values may
    or may not be space separated.
    """
    # The list comprehension implementation is fractionally slower in this case    
    #
    #    hexStr = ''.join( hexStr.split(" ") )
    #    return ''.join( ["%c" % chr( int ( hexStr[i:i+2],16 ) ) \
    #                                   for i in range(0, len( hexStr ), 2) ] )
 
    bytes = []

    hexStr = ''.join( hexStr.split(" ") )

    for i in range(0, len(hexStr), 2):
        bytes.append( chr( int (hexStr[i:i+2], 16 ) ) )

    return ''.join( bytes )




#-------------------------------------------------------------------------------------
# CONVERSION utilities
#-------------------------------------------------------------------------------------
def toUnsignedBytes(signedBytes):
    """ Convert a signed bytes array (java bytes) to unsigned bytes array """    
    listStr = []
    for i in signedBytes : 
        if i == -128:
            i = 128
        if i > -128 and i < 0:
            i = 256 + i
        listStr.append(i)
    return listStr

def convertStringToBytes(hexstr):
    '''
       convert a string of 2 hex bytes strings to a bytes array
    @param hexstr: a string of form AEFF0134 ...
    '''
    '''bytes = jarray.zeros(len(hexstr) / 2, 'b')
    for i in xrange(0, len(bytes), 2):
        bytes[i / 2] = int('0x' + str[i:i + 2], 0)
    return bytes'''
    bytes=[]
    for i in range(0, len(hexstr)/ 2):
        val = int('0x' + hexstr[i*2:i*2+2], 0)
        if val > 128: val = val-256
        bytes.append(val)
    return bytes

def convertBytesToString(theBytes):
    '''
        Transform a java signed bytes array into a string of Hex bytes of the form
        AAEF00FE01 ...
    @param bytes: java signed bytes
    '''
    string = ''    
    if not theBytes: return string
    return ''.join( '%.2X' % b  for b in toUnsignedBytes(theBytes)).upper()

# from http://code.activestate.com/recipes/510399-byte-to-hex-and-hex-to-byte-string-conversion/ END

# def convertBytesToString(bytes):
#     '''
#         Transform a java signed bytes array into a string of Hex bytes of the form
#         AAEF00FE01 ...
#     @param bytes: java signed bytes
#     '''
#     strTmp = ''    
#     if not bytes: return strTmp
#     for b in bytes:
#         strTmp = strTmp + ("%2s" % hex(ord(b))[-2:].replace('x', '0', 1))
#     return strTmp.replace(" ", "0").upper()


def getidFormat():
    """ return a string that defines a common ID format for each transaction.
        It is composed of the Run ID ( processID.threadID.runID )
        to which ".lineID" is added ( defining the fullRunID )
        lineID being current line number treated by one implementation.
        in toolbox to have a common place for the definition.
        """
    return idFormat

def getRunIDPadding():
    """ returns the length of the padding for the full run ID part of 
        return the fullRunID padding length to which the lineID addition is removed.
        in toolbox to have a common place for the definition.
    """ 
    return runIDPadding

#
#==============================================================================================
#  Some tests function on timing
#==============================================================================================
#
def fast():
    """Wait 0.001 seconds.
    """
    time.sleep(1e-3)
def slow():
    """Wait 0.1 seconds.
    """
    time.sleep(0.1)

def use_fast():
    """Call `fast` 100 times.
    """
    for _ in xrange(100):
        fast()


def use_slow():
    """Call `slow` 100 times.
    """
    for _ in xrange(100):
        slow()


@contextmanager
def timing(verbose=False):
    start = time.time()
    yield
    secs=time.time()-start
    msecs=secs*1000
    if verbose:
        print 'elapsed time: %f ms' % msecs
    
class Timer(object):
    def __init__(self, name=None, verbose=False):
        self.verbose = verbose
        self.name=name

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.secs = self.end - self.start
        self.msecs = self.secs * 1000  # millisecs
        if self.verbose:
            logger.debug('%s - elapsed time: %f ms' % ('%s' % self.name if self.name else '',self.msecs))

        
if __name__ == '__main__':
    with Timer() as t:
        use_fast()
    print "=> elasped : %s s %s msec" % (t.secs,t.msecs)

    with timing(True) as t:
        use_fast()

    
    with timing(True) as t:
        use_slow()

    with Timer() as t:
        use_slow()
    print "=> elasped : %s s %s msec" % (t.secs,t.msecs)
        
# EXAMPLE OF USAGE:
#=====================
#         # immutable macros object
#         with Timer('getMacrosInstances',True):
#             self.macrosCached = CachedMacros.getMacrosInstances()
#         
#         for k in self.macrosCached:
#             for x in self.macrosCached[k]:
#                 print 'getMacrosInstances [thread=%d] [%s] [id=%s] [type=%s]' % ( grinder.threadNumber, self.macrosCached[k][x], id(self.macrosCached[k][x]), type(self.macrosCached[k][x]) )  
#         
#         with Timer('copyMacros',True):
#             self.macrosCached = CachedMacros().copyMacros()
#         
#         for k in self.macrosCached:
#             for x in self.macrosCached[k]:
#                 print 'copyMacros [thread=%d] [%s] [id=%s] [type=%s]' % ( grinder.threadNumber, self.macrosCached[k][x], id(self.macrosCached[k][x]), type(self.macrosCached[k][x]) )  
        
            
            

