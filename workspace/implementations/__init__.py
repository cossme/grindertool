import traceback
import sys
from net.grinder.script.Grinder import grinder

if grinder:
    properties=grinder.properties

def init():
    import os
     
    for module in os.listdir(__path__[0]):
        if module.endswith('.py') and not module.startswith('_'):
            try:
                __import__(__name__+'.'+module[:-3])
            except ImportError, e:
                if __name__ in ('smpp'): 
                    if not properties.getBoolean('grindertool.smsc.start',False):
                        print 'Ignoring %s loading' % (__name__)
            except Exception, e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                errorMsg=repr(traceback.format_exception(exc_type, exc_value,exc_traceback))
                print errorMsg
                print '=====> import error for module %s <====== Reason: "%s"' % (module[:-3], e)
                raise e                

init()