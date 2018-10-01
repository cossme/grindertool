'''
Created on Jan 18, 2012

@author: afabri
'''
import os

from net.grinder.script.Grinder import grinder
from org.cossme.tsm.jschssh import ExecSsh
from java.io import FileInputStream
from java.util import Properties
from java.nio.charset import Charset;
from java.nio.file import Files;
from java.nio.file import Paths;


import java
import inspect
import traceback
import sys


from java.lang import StringBuffer
from core import core

#----------------------------------------------------------------------
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
#----------------------------------------------------------------------

class procexec(core):
    '''
        A generic shell command executor
    '''
    def __init__(self,_dataFilePath, _templateFilePath):
        core.__init__(self, _dataFilePath, _templateFilePath)

    def loadPropertyFile(self,propertyFile):
        lines = Files.readAllLines(Paths.get(propertyFile), Charset.forName("UTF-8"))
        return lines


    def getValue(self,name,data,context,default):
        if logger.isTraceEnabled():
            (file_name,method_name)=self.traceInitialize()
        if name in data:
            return data[name]
        elif context.get(name) != None:
            return context.get(name)
        else:
            return default

    def traceInitialize(self,traceMe=False):
        file_name=""
        method_name=""
        if logger.isTraceEnabled():
            frame=inspect.currentframe()
            try:
                file_name=frame.f_back.f_code.co_filename.split('/')[-1].split('.')[0]
                method_name=frame.f_back.f_code.co_name
            finally:
                del frame
            if traceMe:
                logger.trace("%s %s called" % (file_name, method_name))
        return (file_name,method_name)

    def updateDataFromContext(self,data,context):
        self.host=self.getValue('host',data,context,None)
        self.port=self.getValue('port',data,context,None)
        self.commands=self.getValue('commands',data,context,None)
        self.identityPath=self.getValue('identityPath',data,context,None)
        self.propertyFile=self.getValue('propertyFile',data,context,None)
        if self.commands:
            if type(self.commands) is list:
                cmdlist=[]
                for cmd in self.commands:
                    cmdlist=cmdlist+[cmd[key] for key in cmd.keys() if key == 'cmd']
                self.commands=cmdlist


    def callCommand(self,data,context):
        """
           - add store to the client
           - add synchronization data
           - launch synchronization
        """
        self.debug('callCommand begin' )

        try:
                env=None
                if self.propertyFile:
                    env = self.loadPropertyFile(self.propertyFile)

                resultTxt = StringBuffer()
                sshexec = ExecSsh()
                retVal = sshexec.runCommand(self.host, self.port, self.commands, self.identityPath, env, resultTxt)

                liResp = {}
                liResp['httpStatCode'] = str(retVal)
                liResp['responseText'] = resultTxt.toString()
                liResp['errorCode'] = 500
                if not ((str(retVal)) == '500'):
                    liResp['errorCode'] = 0

                print 'INFO: return code=%d' % (retVal)
                print 'INFO: return text=%s' % (resultTxt)

        except Exception, ex:

                logger.error('Implementation failed, reason: %s' % (ex))

                # traceback

                exc_type, exc_value, exc_traceback = sys.exc_info()

                errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))

                logger.error(errorMsg)

                errMsg="Unable to send data, reason: %s" % (ex)
                logger.error(errMsg)
                liResp['errorCode']=500
                liResp['responseText']=errMsg


        self.debug('callCommand end' )

        return liResp


    def sendData(self, **args ):
        if logger.isTraceEnabled():
            logger.trace('sendData - data: %s' % (args['data']))
            logger.trace('sendData - context: %s' % (args['context']))
            logger.trace('sendData - memorizedFlag: %s' % (args['memorizedFlag']))
        self.updateDataFromContext(args['data'],args['context'])
        return self.callCommand(args['data'],args['context'])


