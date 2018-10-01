from __future__ import with_statement
from threading import Condition

class Trace():

    hash={}
    mutex=Condition()
    
    @classmethod
    def openFile(cls,filename):
        with cls.mutex:
            if filename not in cls.hash:
                cls.hash[filename] = open(filename, 'w')
        
        
    def __init__(self, filename):
        self.filename=filename
        self.__class__.openFile(filename)
        
    
    def tprint(self, data):
        with self.__class__.mutex:
            try:
                self.__class__.hash[self.filename].write('%s\n' % (data))
                self.__class__.hash[self.filename].flush()
                return data
            except KeyError:
                raise SyntaxError('file %s not found')


    def __del__(self):
        with self.__class__.mutex:
            if self.__class__.hash[self.filename]:
                self.__class__.hash[self.filename].close()
                self.__class__.hash[self.filename]=None

def initialize(filename):
    instance = Trace(filename)
    return instance

if __name__ == "__main__":
    file1 = initialize('c:/temp/test.txt')
    file2 = initialize('c:/temp/test2.txt')
    a=file1.tprint('toto')
    print 'a='+a
    a=file2.tprint('toto')
    print 'a='+a
    b=file2.tprint('titi')
    print 'b='+b
    b=file1.tprint('titi')
    print 'b='+b
    