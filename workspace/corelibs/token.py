'''
Created on 30 juil. 2014

@author: omerlin
'''
from java.lang import System


class AbortRunToken:
    '''
      An empty token async error management
    '''
    def __init__(self):
        pass


class StartToken:
    '''
      An empty token for debug purpose
    '''
    def __init__(self):
        pass

class Token:
    '''
    Token are just plain object with 2 parameters
    
    :param  time_to_sleep: a time to deliver message to a Queue()
            internal dictionary: _params, a structure that store hash keys value
                                 the hash keys value are initialized during the setValue(self,parameter) 
    '''
    def __init__(self, time_to_sleep):
        self.time_to_sleep=time_to_sleep
        self.timestamp=System.currentTimeMillis()
    def count(self):
        return len(self._params)
    def getInterval(self):
        return self.time_to_sleep
    def getTimestamp(self):
        return self.timestamp
    def getIncrement(self):
        return 1
    def __repr__(self):
        return '[time_to_sleep=%d][timestamp=%s]' % (self.time_to_sleep, self.timestamp)

class ThroughputToken(Token):
    '''
      Just to distinguish Token provider from another king of Token provider.
    '''
    def __init__(self,time_to_sleep, wait=False):
        Token.__init__(self, time_to_sleep)
        self.wait=wait
    def __repr__(self):
        return '[wait=%s][time_to_sleep=%d][timestamp=%s]' % (self.wait,self.time_to_sleep, self.timestamp)


class InternalBatchToken():
    '''
       Group run tokens in batch to release the single producer bottleneck
       These tokens are internal to the metronom producer.
    '''
    def __init__(self,batchSize, deltatime):
        '''
        :param batchSize: number of "runs" token
        :param deltatime: the time interval at the given throughput
        '''
        self.increment=batchSize
        self.deltatime=deltatime
        
        # list of token run time delta 
        self.data=[]
        [self.data.append(long(i*deltatime)) for i in xrange(batchSize)]
        
        self.time_to_sleep=long(batchSize*deltatime)
        
    def getIncrement(self):
        return self.increment
    
    def getInterval(self):
        return self.time_to_sleep
     
    def __repr__(self):
        return 'InternalBatchToken [batchSize=%d][deltaTime=%6.2fms][TotalSleep=%d]' % (self.increment, self.deltatime, self.time_to_sleep)



class ContextToken(Token):
    '''
       Abstract context token for asynchronous flow
    '''
    def __init__(self, contextKey, value, data=None, time_to_sleep=0):
        Token.__init__(self, time_to_sleep)
        self.context={'contextKey':contextKey,'value':value,'data':data}
    def get(self):
        return self.context
    def getContextKey(self):
        return self.context['contextKey']
    def getContextValue(self):
        return self.context['value']
    def getValue(self):
        return self.context['value']
    def getContextData(self):
        return self.context['data']
    def __repr__(self):
        return '[contextKey=%s][value=%s][data=%s]' % (self.context['contextKey'],self.context['value'],self.context['data'])

class AsyncContextToken(ContextToken):
    def __init__(self, contextKey, value, data, time_to_sleep=0):
        ContextToken.__init__(self, contextKey, value, data, time_to_sleep)

class SMPPToken(ContextToken):
    def __init__(self, contextKey, value, data, time_to_sleep=0):
        ContextToken.__init__(self, contextKey, value, data, time_to_sleep)

class HttpToken(Token):
    def __init__(self,time_to_sleep=0):
        Token.__init__(self, time_to_sleep)
        self._params={}
    def setValue(self, url_string):
        '''
        Extract all the parameters from an url string
        :param url_string: an encoded url (urllib.quote_plus() for instance)
        '''
        pos = url_string.find('?')
        s=url_string[pos+1:] if pos else url_string
        for k in s.split('&'):
            pos=k.find('=')
            self.setValueHash(k[:pos],k[pos+1:])

    def setValueHash(self, arg1,val1):
        '''
            Add a value in the hash
        '''
        self._params[arg1]=val1
    def getValues(self):
        return self._params
    def getTags(self):
        ''' for templating substitution '''
        return self._params.keys()
    def __repr__(self):
        s=''.join("[%s=%s]" % (k,v) for k,v in self._params.iteritems())
        return '[time_to_sleep=%d][timestamp=%s][s=%s]' % (self.time_to_sleep, self.timestamp,s)
