'''
Created on Oct 10, 2010

@author: omerlin
'''
from __future__ import with_statement
from threading import Lock
import unittest

class listGenerator(object):
    
    index=0
    lockSession=Lock()
    elems=[]
    
    def __init__(self, strArgs, separator=','):
        '''
           a sting of element to cycle separate by a ',' by default
        '''
        self.__class__.elems =  [x for x in strArgs.split(separator)]
        
    def next(self):
        return self.getValue()
    def getValue(self):
        with self.__class__.lockSession:
            if self.__class__.index >= len(self.__class__.elems):
                self.__class__.index=0
            
            elem=self.__class__.elems[self.__class__.index]
            self.__class__.index+=1
            return elem

    def __repr__(self):
        return 'elems=%s' % (self.__class__.elems)
    

def initialize(strArgs):
    instance = listGenerator(strArgs)
    return instance

class Test(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    
    def title(self):
        s='Running : %s' % (self.id())
        print 
        print s
        print '='*len(s)
        
    def testBasicCycling(self):
        self.title()
        i1=initialize('tenant1,tenant2,tenant3,tenant4')
        for _ in range(100):
            print i1.next()
        

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=2).run(suite)
    