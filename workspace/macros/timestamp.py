"""
Generic utils functions

Created 07.05.2014

"""
from time import strftime
import time

class timestamp:
    
    def __init__(self, tsformat):
        self.tsformat = tsformat
        try:
            if len(self.ctd(self.tsformat)) == 0:
                raise SyntaxError('Timestamp format empty')
        except Exception, e:
            raise SyntaxError('Timestamp format in input file is incorrect: %s' %  e)
    
    def ctd(self, x):
        timeformat = x
        y = time.strftime(timeformat)
        return y
    
    def get(self, MTstring):
        gettime = self.ctd(self.tsformat)
        return gettime

def create(timestampformat):
    instance = timestamp(timestampformat)
    return instance


if __name__ == '__main__':
    print "Timwstamp cannot be used as a standalone program"
