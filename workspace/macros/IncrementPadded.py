from threading import Condition


class Increment:
    cv_increment=Condition()
    inc=None
    def __init__(self, strArgs):
        try:
            (inc,self.padding) =  [int(k) for k in strArgs.split(',')]
        except Exception, x:
            raise SyntaxError("%s initialization failed, we expect two parameters, separated by coma. you gave '''%s'''\n %s"
                              %(self.__class__, strArgs, x))
        if not self.__class__.inc:
            self.__class__.cv_increment.acquire()
            if not self.__class__.inc:
                try:
                    self.__class__.inc=inc
                except Exception, ex:
                    raise SyntaxError('%s init string - bad initialization, error: %s' % (strArgs, ex))
            self.__class__.cv_increment.release()

    def __repr__(self):
        return __name__

    def getValue(self):
        self.__class__.cv_increment.acquire()
        self.__class__.inc+=1
        retval=str(self.__class__.inc).zfill(self.padding)
        self.__class__.cv_increment.release()
        return retval

    def getName(self):
        return self.__class__.__name__

def initialize(strArgs):
    instance = Increment(strArgs)
    return instance

if __name__ == '__main__':
    print "Cannot be used as a standalone program"

