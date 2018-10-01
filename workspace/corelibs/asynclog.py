#!/usr/bin/env python
# -*- coding: utf-8 -*-
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
class asynclog:
    @classmethod
    def __format(cls, **kargs):
        try:
            return '%s<<ASYNC>>[%s=%s]%s[%s] %s' % ('[uid=%s]' % (kargs['uid']) if 'uid' in kargs else '', kargs['key'] if 'key' in kargs else 'No key',
                                                    kargs['value'] if 'value' in kargs else 'No value',
                      'ctx(%s):[%s=%s]' % (hex(id(kargs['ctx'])),kargs['ctx'].contextKey,kargs['ctx'].contextValue) if 'ctx' in kargs else '', 
                                                    kargs['pos'] if 'pos' in kargs else 'Not located',kargs['msg'] if 'msg' in kargs else 'No message')
        except Exception, e:
            logger.error('asynclog.__format() error with kargs=%s' % (kargs))
            raise e
    @classmethod
    def __formatError(cls, **kargs):
        return '%s, reason: %s' % (cls.__format(**kargs), kargs['err']) 
    @classmethod
    def logDebug(cls, **kargs):
        if logger.isDebugEnabled():
            logger.debug(cls.__format(**kargs))
    @classmethod
    def log(cls, **kargs):
        cls.logDebug(**kargs)
    @classmethod
    def logInfo(cls, **kargs):
        if logger.isInfoEnabled():
            logger.info(cls.__format(**kargs))
    @classmethod
    def logTrace(cls, **kargs):
        if logger.isTraceEnabled():
            logger.trace(cls.__format(**kargs))
    @classmethod
    def logError(cls, **kargs):
        logger.error(cls.__formatError(**kargs))
    @classmethod
    def logWarning(cls, **kargs):
        logger.warn(cls.__formatError(**kargs))
