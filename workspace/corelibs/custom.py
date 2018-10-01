"""
    Custom entry point for logging
"""
import xmlrpclib
from corelibs.toolbox import AbstractLogger


class CustomLogger(AbstractLogger):
        
    def __init__(self, param=None):
        try:
            self.logger = xmlrpclib.ServerProxy(param)
        except Exception,e:
            self.logger=super(CustomLogger, self).getLogger()
            self.logger.error('XMLRPC server not started or bad configuration (url=%s), cause: %s' % (param,e))
    
    def log_failure (self,*args,**kwargs):
        failure_id = self.logger.log_failure( dict((k, v) for k, v in kwargs.iteritems() if v))
        return failure_id
    
    def info(self, *args, **kargs):
        d={'failure':self.log_failure,'startScenario':self.logger.start_scenario,
           'endScenario':self.logger.endScenario}
        d[args[0]](args[1:],**kargs)
#         if args[0]=='failure':
#             self.log_failure(*args,**kargs)
#         elif args[0]=='startScenario':
#             self.collector.start_scenario(args[1:])

