import xmlrpclib
import os

def get_proxy(url=None):
    if (url):
        return collector_instance(url)
    else:
        return fake_proxy()


class collector_instance:
    def __init__(self, url, tracefile='./logtrace.txt'):
        self.collector = xmlrpclib.ServerProxy(url)
        self.tracefh =  open(tracefile, 'w')

    def log_test_result(self, *args, **kwargs):
        self.tracefh.write ("\n")
        for k in kwargs:
            self.tracefh.write("%s -> %s\n" % (k, kwargs[k] ))
        result_id = self.collector.log_test_result(dict((k, v) for k, v in kwargs.iteritems() if v))
        return result_id

    def __getattr__(self, name):
        return self.collector.__getattr__(name)


class fake_proxy:
    def __init__(self):
        pass

    def __str__(self):
        return "Fake proxy class"

    def __getattr__(self, name):
        return lambda self, *args, **kwargs: None


proxy=get_proxy('http://127.0.0.1:%s/RPC2' % (8000 if not 'LOG_COLLECTOR_PORT' in os.environ else int(os.environ['LOG_COLLECTOR_PORT'])))
proxy.write_results_nice(1,'MyTestCase','MyTestResults_1.xml')
