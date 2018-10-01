def init():
    import os
     
    for module in os.listdir(__path__[0]):
        if module.endswith('.py') and not module.startswith('_'):
            try:
                __import__(__name__+'.'+module[:-3])
            except:
                print 'ERROR (not ignored) - import error for module %s' % (module[:-3])
                raise
 
init()