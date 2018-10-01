"""
  Sql protocol implementation
"""

from java.sql import DriverManager
from javax.xml.bind.DatatypeConverter import printHexBinary
from java.lang import Class
import java.sql.Types as Types

from core import core

#----------------------------------------------------------------------
from corelibs.coreGrinder import CoreGrinder
properties=CoreGrinder.getProperty()
logger=CoreGrinder.getLogger()
grinder=CoreGrinder.getGrinder()


class SimpleObject(object):
    
    def __init__(self, array):
        self.content = array
    
    @classmethod
    def fromByteArray(cls,array):
        #Object creation
        return cls(array)
    
    def len(self):
        return len(self.content)
    
    def isValid(self):
        return True
    
    def __str__(self):
        return printHexBinary(self.content) if self.content else 'None'

class Apdu(SimpleObject):
    
    def __str__(self):
        return 'Apdu command:' + printHexBinary(self.content) if self.content else 'None'
        
    
class DumbObject(SimpleObject):
    
    def __str__(self):
        return 'Dumb Object'

def intDumper (i):
    return lambda rs: "*" * rs.getInt(i)

def apduDumper(i):
    return lambda rs: printHexBinary(rs.getBytes(i)) 

def dateDumper(i):
    return lambda rs: rs.getDate(i).toString()

def stringDumper(i):
    return lambda rs: rs.getString(i)

def apduDumper2(i):
    return lambda rs: Apdu.fromByteArray(rs.getBytes(i))

def nullDumper(i):
    return lambda rs:rs.getString(i)

def objectDumper(mytype):
    def dumper (i):
        return lambda rs: mytype.fromByteArray(rs.getBytes(i))
    return dumper

defaultTrans = { Types.INTEGER: intDumper, Types.BLOB: objectDumper(Apdu), Types.VARCHAR: stringDumper}

def transFromMeta(metadata):
    for i in range(1,1+metadata.getColumnCount()):
        col_type = metadata.getColumnType(i)
        logger.trace('Type of column %d: %s' % (i, col_type))
        if col_type in defaultTrans:
            yield defaultTrans[col_type](i)
        else:
            yield nullDumper(i) 


def headerGenerator(metadata):
    for i in range(1,1+metadata.getColumnCount()): yield metadata.getColumnName(i)

def rowGenerator(results, foreachrow):
    while results.next():
        translator = transFromMeta(results.getMetaData()) # TODO: Trans func recycling
        yield foreachrow ([ i(results) for i in translator ])

def yamlRowGenerator(results):
    rowgen= rowGenerator(results, lambda x: [ str(k)+":"+str(v) for (k,v) in zip (headerGenerator(results.getMetaData()),x)])
    for i in rowgen: yield "\n\t".join(i)
    
def XmlRowGenerator(results):
    rowgen= rowGenerator(results, lambda x: [ "\t<"+str(k)+">"+str(v)+"</"+str(k)+">" for (k,v) in zip (headerGenerator(results.getMetaData()),x)])
    for i in rowgen: yield '<record>\n'+ "\n".join(i) + '</record>'
    
def stringRowGenerator(results,sep='|'):
    return rowGenerator(results, sep.join)
    
def simpleQuery(strArgs):
    jdbc_url="jdbc:sqlite:/root/test.db"
    DriverManager.registerDriver(Class.forName("org.sqlite.JDBC").newInstance())
    connection=DriverManager.getConnection(jdbc_url, "", "")
    statement=connection.createStatement()
    results=statement.executeQuery(strArgs)
    #res= "\n".join (rowGenerator(results, '|'.join))
    #res= "\n".join (rowGenerator(results, lambda x: str(len (x))))
    res= "\n".join (stringRowGenerator(results, sep='\n'))
    return res

def singleApduQuery(strArgs):
    jdbc_url="jdbc:sqlite:/root/test.db"
    DriverManager.registerDriver(Class.forName("org.sqlite.JDBC").newInstance())
    connection=DriverManager.getConnection(jdbc_url, "", "")
    statement=connection.createStatement()
    results=statement.executeQuery(strArgs)
    res = rowGenerator(results, lambda x: x.pop())
    return res

def simpleXmlQuery(strArgs,caller):
    DriverManager.registerDriver(Class.forName(caller.jdbc_driver).newInstance())
    connection=DriverManager.getConnection(caller.jdbc_url, caller.jdbc_user, caller.jdbc_pass)
    statement=connection.createStatement()
    results=statement.executeQuery(strArgs)
    res= '<xml>\n' + "\n".join (XmlRowGenerator(results)) + '\n</xml>' 
    return res

def simpleXmlUpdate(strArgs,caller):
    DriverManager.registerDriver(Class.forName(caller.jdbc_driver).newInstance())
    connection=DriverManager.getConnection(caller.jdbc_url, caller.jdbc_user, caller.jdbc_pass)
    statement=connection.createStatement()
    results=statement.executeUpdate(strArgs)
    res= str(results)
    return res


class sql(core):
 
    
    def __init__(self,_dataFilePath, _templateFilePath):       
        core.__init__(self, _dataFilePath, _templateFilePath)
        self.min_random=grinder.getProperties().getInt('dummy.sleep.min',0)
        self.max_random=grinder.getProperties().getInt('dummy.sleep.max',0)
        if self.min_random>self.max_random:
            self.error('Parameter dummy.sleep.min [%d] and dummy.sleep.max [%d] are not consistent ! ' % (self.min_random,self.max_random))
            raise
        self.sleep=True if self.min_random>0 and self.max_random>0 else False  
        properties=grinder.getProperties()
        self.displayReadResponse = properties.getBoolean('displayReadResponse',False)


       
    def version(self):
        ''' header string inserted by MKS - parse the second field (file name) and the third field (version)
        and concatenate the two together to create a version string
        return the release string'''
        setVersion = '$Header: dummy.grindertool 1.3 2011/06/15 15:52:15CEST omerlin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    
    def sendData(self,**args):
        # THIS IS REALLY UGLY 
        self.jdbc_driver = properties.get('sql.jdbc_driver')
        self.jdbc_url = properties.get('sql.jdbc_url')
        self.jdbc_user = properties.get('sql.jdbc_user')
        self.jdbc_pass = properties.get('sql.jdbc_pass')
        #######################
        data = args['data']
        if (isinstance(data, dict)):
            #NOT using template
            sql = data['query']
        else:
            #Using template
            config = self.setProperties(args['data'])
            sql = config['request0.query']

        if sql.upper().startswith('INSERT') or sql.upper().startswith('UPDATE') or sql.upper().startswith('DELETE') or sql.upper().startswith('DROP') or sql.upper().startswith('CREATE') or sql.upper().startswith('ALTER') or sql.upper().startswith('TRUNCATE'):
            res = simpleXmlUpdate(sql,self)
        else: 
            res = simpleXmlQuery(sql,self)
            
        if logger.isInfoEnabled():
            logger.info('%sMessage=%s' % ("<" * 5, sql))
            # logger.info('%sMessage=%s' % (">" * 5, res))
            if self.displayReadResponse:
                print '%s sent = %s' % ("<" * 5, sql)
                # print '%s rec  = %s' % (">" * 5, str(res))
        #print res
        liResp = {'httpStatCode':'200',
                   'responseText':str(res),
                   'message':args['data'],
                   'errorCode':'200' }
        logger.debug('Message=%s' % res)
        return liResp
        
