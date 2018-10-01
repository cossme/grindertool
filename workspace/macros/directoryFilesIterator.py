import os
from threading import Lock


debug=False
cv = Lock()

class directoryFilesIterator:

    files=[]
        
    def __init__(self, strArgs):
        ''' 
        '''
        (self.fullpath, self.nbThreads) =  strArgs.split(',')
        self.nbThreads=int(self.nbThreads)
        self.counter=0
        cv.acquire()
        if len(self.__class__.files)==0:
            for f in os.listdir(self.fullpath):
#                 if os.path.splitext(f)[-1].upper()[1:] in ('JPG','JPEG','TIFF','BMP'):
                self.__class__.files.append(f)
        cv.release()
        
    def print_all(self):
        for f in self.__class__.files:
            print f
            
    def __repr__(self):
        return '[files count=%d]' % (self.counter)
    
    def getValue(self, strArgs ):
        '''
          x = grindertool.threadNumber
          y = grindertool.runNumber
        '''
        
        (x,y)=[int(k) for k in strArgs.split(',')]
        return '%s%s%s' % (self.fullpath, os.sep, self.__class__.files[x+y*self.nbThreads])
        
    def getName(self):
        return self.__class__.__name__
    

def initialize(strArgs):
    '''    
    '''
    feeder = directoryFilesIterator(strArgs)
    return feeder

if __name__ == "__main__":
    feeder = initialize('c:/tmp/file,2')
    print feeder.getValue('1,1')
