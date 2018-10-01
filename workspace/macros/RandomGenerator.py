'''
  an example of dummy macro
  Please note that interface conventions are required by grindertool.
'''
import random
class RandomGenerator:
    '''
    The actual name of this class should be similar to the .py file
    Access to the class name are only done through the factory function.
    '''
    def __init__(self, strArgs):
        ''' 
        '''
        try:
            (self.min,self.max) =  [int(k) for k in strArgs.split(',')]
        except Exception, x:
            raise SyntaxError("%s initialization failed, we expect two parameters, separated by coma. you gave '''%s'''\n %s" 
                              %(self.__class__, strArgs, x))
                
    def __repr__(self):
        return __name__

    def getRandomValue(self):
        return str(random.randint(self.min,self.max))
    
    def getValue(self):
        return str(random.randint(self.min,self.max))
        
    def getName(self):
        return self.__class__.__name__
    

def initialize(strArgs):
    '''
    initialize is the factory for this macro. It should return an instance of the RandomGenerator class.
    note that you have to obey the interface.
    :Parameters:
      - `strArgs`: contains the string from in between the template parentheses
    :Returns: Instance of TestMacro1 for later use.
    '''
    instance = RandomGenerator(strArgs)
    return instance

if __name__ == '__main__':
    print 'no main for this macro'