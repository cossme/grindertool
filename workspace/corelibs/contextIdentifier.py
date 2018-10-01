'''
Created on 30 juil. 2014

@author: omerlin
'''
from __future__ import with_statement

from threading import Condition, Thread
import time

from corelibs.asynclog import asynclog
from corelibs.contextLock import ContextLock
from corelibs.coreGrinder  import CoreGrinder


logger=CoreGrinder.getLogger()

'''
   A context storage base on a hash of hash
   first level is the identifier (contextKey)
   The second level key is the value of the contextKey.
   The second level value is a  Context() object
'''
class ContextIdentifier:
    
    hash={}
    mutex=Condition()
    reaperThread = None
    stopReaperThread=False
    threadStarted=False
    
        
    @classmethod
    def start(cls):
        cls.reaperThread = Thread( target=cls.reaperLoop, name="ContextIdentifierReaperThread")
        cls.stopReaperThread=False
        cls.reaperThread.start()
        cls.threadStarted=True
        
    @classmethod
    def stop(cls):
        if cls.reaperThread is not None:
            cls.stopReaperThread=True
    
         
    @classmethod
    def isLocked(cls, key, value):
        '''
        check if cache resource is locked
        '''
        try:
            with cls.mutex:
                asynclog.log(pos='%s.isLocked' %(cls.__name__), key=key,value=value, msg='lock flag set' )
                return cls.hash[key][value].isLocked()
        except KeyError,e:
            # This could happen if entry was removed from cache
            asynclog.logWarning(pos='%s.isLocked' %(cls.__name__), key=key,value=value, msg='unlock flag', err=str(e))
            pass
        except Exception, e:
            asynclog.logError(pos='%s.isLocked' %(cls.__name__), key=key,value=value, msg='unlock flag', err=str(e))
        # if the key/value doesn't exists - it has been swept
        return False

    @classmethod
    def unlock(cls, key, value):
        '''
        check if cache resource is locked
        '''
        try:
            with cls.mutex:
                asynclog.log(pos='%s.unlock' %(cls.__name__), key=key,value=value, msg='unlock flag' )
                return cls.hash[key][value].unlock()
        except KeyError, e:
            # This could happen if entry was removed from cache
            asynclog.logWarning(pos='%s.unlock' %(cls.__name__), key=key,value=value, msg='unlock flag', err=str(e))
        except Exception, e:
            asynclog.logError(pos='%s.unlock' %(cls.__name__), key=key,value=value, msg='unlock flag', err=str(e))
        # if the key/value doesn't exists - it has been swept
        return False


        
    @classmethod
    def add_ctx(cls, key, value, clonedContext):
        '''
           Add a Context() instance to the hash of hash
        :param contextKey: first hash level
        :param value: second hash level
        :param contextInstance: the value for the second level of type Context()
        '''
        try:
            with cls.mutex:
                if not key in cls.hash:
                    cls.hash[key] = {}
                
                # Set a functional lock from callback_before()
                clonedContext.setLock()
                cls.hash[key][value] = clonedContext
                
                asynclog.log(pos='%s.add_ctx' %(cls.__name__), key=key,value=value, msg='storing context',ctx=clonedContext )
                
        # No ERROR logger trace here, as it is reported one level up
        except Exception, e:
            asynclog.logError(pos='%s.add' %(cls.__name__), key=key,value=value, msg='storing context failed',err=str(e),ctx=clonedContext )
            raise e

    @classmethod
    def put(cls, contextKey, value, contextInstance):
        cls.add(contextKey, value, contextInstance)

    @classmethod
    def update(cls, key, value, dictData):
        '''
           update data to an existing context
        :param contextKey: first hash level
        :param value: second hash level
        :param dictData: a dictionary of data ( resulting  from a memorize() evaluation ) 
        '''
        try:
            with cls.mutex:        
                cls.hash[key][value].getCacheKeys().update_keys_permanently(dictData)
                asynclog.log(pos='%s.update' %(cls.__name__), key=key,value=value, msg='update notification data permanently' )
        except Exception, e:
            asynclog.logError(pos='%s.update' %(cls.__name__), key=key,value=value, msg='update notification data permanently',err=str(e) )
            raise e

    @classmethod
    def updateCache(cls,__ctx):
        key,value=__ctx.contextKey,__ctx.contextValue
        try:
            with cls.mutex:
                # get DictRuntime keys
                __data=cls.hash[key][value].getCacheKeys().get()
                
                if logger.isTraceEnabled():
                    asynclog.logTrace(pos='%s.updateCache' %(cls.__name__), key=key,value=value, msg='update with callback cache. data: %s' % (__data) )
                # Merge with current context REF cache 
                __ctx.getCacheKeys().update_asyncData_permanently(__data)
                return cls.hash[key][value].getCacheKeys()
        except Exception, e:
            asynclog.logError(pos='%s.updateCache' %(cls.__name__), key=key,value=value, msg='update callback cache',err=str(e) )
            
    @classmethod
    def lock_and_update_flag(cls, __ctx, dictData):
        '''
           update data to an existing context
        :param contextKey: first hash level
        :param value: second hash level
        :param dictData: a dictionary of data ( resulting  from a memorize() evaluation ) 
        '''
        try:
            with cls.mutex:        
                __ctx=cls.hash[__ctx.contextKey][__ctx.contextValue]
                if not __ctx.isLocked():
                    return False
                
                asynclog.log(pos='%s.__manage' %(cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, 
                             ctx=__ctx, msg='LOCK IS UP' )    
                __ctx.setFlag()
                # update dictRuntime data
                __ctx.getCacheKeys().update_keys(dictData)
                asynclog.log(pos='%s.update_and_flag' %(cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, 
                             msg='updated with notification data',ctx=__ctx )
                return True
                
        except Exception, e:
            asynclog.logError(pos='%s.update_and_flag' %(cls.__name__), key=__ctx.contextKey,value=__ctx.contextValue, msg='update notification data permanently',err=str(e) )
            raise e
 
 
    @classmethod
    def isFlagged(cls, key, value):
        '''
            Return the object stored for the 2 levels key,value OR None
            
        :param contextKey: first level
        :param value: second level
        '''
        try:
            __ctx=cls.hash[key][value]
            asynclog.log(pos='%s.isFlagged' %(cls.__name__), key=key,value=value, msg='Flagged: %s' % (str(__ctx.isFlagged())) )
            return __ctx.isFlagged()
        except Exception, e:
            asynclog.logWarning(pos='%s.isFlagged' %(cls.__name__), key=key,value=value, msg='not found !!',err=str(e))
            return None
      
  
    @classmethod
    def exists(cls, key, value):
        '''
            Return the object stored for the 2 levels key,value OR None
            
        :param contextKey: first level
        :param value: second level
        '''
        try:
            if logger.isDebugEnabled():
                asynclog.log(pos='%s.exists' %(cls.__name__), key=key,value=value, msg='check existence',ctx=cls.hash[key][value] )
            return cls.hash[key][value]
        except Exception, e:
            asynclog.logWarning(pos='%s.exists' %(cls.__name__), key=key,value=value, msg='not found !!',err=str(e))
            return None


    @classmethod
    def pop_ctx_value(cls, key,value):
        '''
           find a Context() identified by its 2 levels
           if found, remove from the Context from the hash
        :param contextKey: first level
        :param value: second level
        '''
        try:
            with cls.mutex:       
                asynclog.log(pos='%s.pop_ctx_value' %(cls.__name__), key=key,value=value, msg='')
                return cls.hash[key].pop(value)
        except KeyError:
            if not key in cls.hash:
                logger.error('Key "%s" not defined, check what happens for the value "%s" in the asynchronous.call_after()' % (key,value))
            else:
                logger.error('Key "%s" exists but value "%s" not found - check asynchronous.call_after() at the add() context call' % (key,value))
            return None
        except Exception,e:
            asynclog.logError(pos='%s.pop_ctx_value' %(cls.__name__), key=key,value=value, msg='',err=str(e) )
            return None
     
        
    @classmethod
    def pop_ctx(cls, __ctx):
        '''
           find a Context() identified by its 2 levels
           if found, remove from the Context from the hash
        :param contextKey: first level
        :param value: second level
        '''
        key,value=__ctx.contextKey,__ctx.contextValue
        try:
            with cls.mutex:       
                asynclog.log(pos='%s.pop_ctx' %(cls.__name__), key=key,value=value, msg='',ctx=__ctx )
                return cls.hash[key].pop(value)
        except KeyError:
            if not key in cls.hash:
                logger.error('Key "%s" not defined, check what happens for the value "%s" in the asynchronous.call_after()' % (key,value))
            else:
                logger.error('Key "%s" exists but value "%s" not found - check asynchronous.call_after() at the add() context call' % (key,value))
            return None
        except Exception,e:
            asynclog.logError(pos='%s.pop_ctx' %(cls.__name__), key=key,value=value, msg='',err=str(e) )
            return None
    
    @classmethod
    def getCount(cls, contextKey):
        return len(cls.hash.get(contextKey,{}))
    
    @classmethod
    def getCountAll(cls):
        return [ {k:len(v)} for k,v in cls.hash.iteritems() ]
    
    @classmethod
    def find(cls, contextKey, value):
        cls.get(contextKey, value)

    
    @classmethod
    def clearAll(cls):
        with cls.mutex:       
            cls.hash.clear()
                
    @classmethod
    def printall(cls):
        s='ContextIdentifier content=\n'
        for k,v in cls.hash.iteritems():
            for value in v.keys():
                s+= '\t[contextKey=%s][value=%s]\n' % (k,value)
        return s
        
    @classmethod
    def __repr__(cls):
        return str(cls.getCountAll())

    @classmethod
    def reaperLoop(cls):
        logger.trace( "Context Reaper Thread starting at %d"%time.time())
        while( not cls.stopReaperThread) :
            # First wait 30s
            for _ in range(30):
                time.sleep( 1)
                if cls.stopReaperThread:
                    logger.trace( "Context Reaper Thread stopping at %d"%time.time())
                    return;
            # remove expired contexts
            cls.removeExpiredContext()
            
        logger.trace( "Context Reaper Thread stopping at %d"% (time.time()) )

    @classmethod
    def removeExpiredContext(cls):
        # Parse a copy of the top level cache
        __nbRemovedContext=0
        __currentTime=time.time()
        logger.trace( "Running Reaper at %d"% (__currentTime))
        
        for __ctxKey, __ctxValue in cls.hash.items():
            logger.trace( "Managing context key %s"% (__ctxKey) )
            # parse each values of the context key (sort by timeout)
            for __value, __ctx in sorted( __ctxValue.items(), key=lambda (__k,__v): (__k,__v.expirationTime)):
                # expiration time to seconds (stored in milli seconds)
                _expirationTime= __ctx.expirationTime/1000 if __ctx.expirationTime>0 else __ctx.expirationTime
                
                # Check the expiration time from the value
                logger.trace( "Parsing key=%s; value=%s; expirationTime=%d"%(__ctxKey, __value, __ctx.expirationTime))
                if _expirationTime == -1:
                    logger.trace( "Skipping key=%s; value=%s; reason=no expiration"%( __ctxKey, __value))
                    continue
                if _expirationTime < __currentTime:
                    
                    # the async scenario must be aborted - move to next test case 
                    logger.trace('removeExpiredContext - calling endAsyncScenarioTimeout ...')
                    __ctx.endAsyncScenarioTimeout()
                    
                    logger.trace( "removeExpiredContext - Removing from context key=%s; value=%s; expiration=%d"%( __ctxKey, __value, _expirationTime))
                    cls.hash[__ctxKey].pop(__value)
                    __nbRemovedContext += 1                    
                    
                    # Decrease all asynchronous counters & print value if trace level 
                    ContextLock.decreaseAllCounters('<<ASYNC>> %s.removeExpiredContext()' % (cls.__name__))
                    
                else:
                    logger.trace( "Skipping key=%s; value=%s; expiration=%d; reason=not expired ! "%( __ctxKey, __value, _expirationTime))
        
        logger.info( "Context Reaper Thread has removed %d context"% (__nbRemovedContext) )        

