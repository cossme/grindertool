import xmlrpclib
from corelibs.coreGrinder  import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
 
class proxy:

    class fake_proxy:
        
        def __init__ (self):
            pass
        
        def __str__ (self):
            return "Fake proxy class"
        
        def __getattr__(self, name):
            return lambda self, *args, **kwargs: None

    class collector_instance:
        
        collector=None
        
        def __init__ (self,url):
            if not self.__class__.collector:
                self.__class__.collector = xmlrpclib.ServerProxy(url,allow_none=True)
    
        def log_result (self,*args,**kwargs):
            # workaround - because of the fake_proxy() - lambda
            dummy_arg=args[0]
            # The caller send:
            #            stepname = __ctx.line.getTestName() , state=status, why=cause, scenario=__ctx.scenario.input_file)
            logger.trace('collector_proxy - %s' % (kwargs))
            result_id = self.__class__.collector.log_test_result( kwargs )
            return result_id
        
        def __getattr__(self, name):
            return self.__class__.collector.__getattr__(name)

    loggerProxy=fake_proxy()    
    if properties.getBoolean('grindertool.custom.logger.activate',False):
        logger.info('Activating proxy logger')
        loggerProxy=collector_instance(properties.get('grindertool.custom.logger.url'))
        try:
            loggerProxy.ping('ping')
        except Exception,e:
            logger.error('Remote proxy error, cause: %s' % (e))
            loggerProxy=fake_proxy()

    @classmethod
    def getLoggerProxy(cls):
        return cls.loggerProxy