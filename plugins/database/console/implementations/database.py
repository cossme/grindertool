"""
dummy (empty implementation)
can be used to check configuration
"""

from net.grinder.script.Grinder import grinder

from core import core
#from StringIO  import StringIO
from com.ziclix.python.sql import zxJDBC
from com.ziclix.python.sql.zxJDBC import DatabaseError
#from oracle.jdbc.driver import OracleDriver
from java.util.regex import Pattern
from string import Template

if grinder: 
    logger=grinder.logger

class database(core):
 
    regexp_connection = Pattern.compile('(\w+)/(\w+)@(.+)')
    regexp_word=Pattern.compile('\s*request(\d+)\.(\w+)\s*=') 
    regexp_comment=Pattern.compile('^\s*#')
    regexp_select=Pattern.compile('^\s*select',Pattern.CASE_INSENSITIVE)
    
    def __init__(self,_dataFilePath, _templateFilePath):       
        core.__init__(self, _dataFilePath, _templateFilePath)

        self.lastStmt='OTHER'
        self.db_type=None
        self.connections =  {}
        str_conn = self.properties.get('db_connection') or None
        logger.info('db_connection=%s' % (str_conn))
        self.connection=None
        if str_conn:
            self.connection = self.getConnection(str_conn)
        if self.connection:
            self.connections[str_conn]= self.connection
            self.cursor=self.connection.cursor()
        self.alias=None
        self.dictBind={}
    
    def getConnection(self, str):
        if str in self.connections.keys():
            return self.connections[str]
        
        found = self.regexp_connection.matcher(str)
        if found.find():
            user=found.group(1)
            password=found.group(2)
            url=found.group(3)
            driver=None
            if url.find('oracle')>0:
                # jdbc:oracle:thin:
                self.db_type='oracle'
                driver="oracle.jdbc.driver.OracleDriver"
            if url.find('mysql')>0:
                self.db_type='mysql'
                driver="org.gjt.mm.mysql.Driver"
            try:
                logger.info('Trying to Connect to %s,%s,%s,%s' % (url, user, password, driver))
                conn = zxJDBC().connect("%s"% url, user, password, driver)
                logger.info('Connected to %s,%s,%s,%s' % (url, user, password, driver))
            except DatabaseError,e:
                raise e     
            self.connections[str] = conn
            return conn
        else:
            print 'Invalid DB url : %s, should be of the form <user>/<passwd>@<dburl>' % (str)
            raise
    
    def executeSQL(self, request):
        logger.debug('request=%s' % (request))
        failure=False
        err=None
        args=''
        fields = request.split('@@')
        print str(fields)        
        stmt = fields[0]
        if len(fields)>1:
            args = Template(fields[1]).substitute(self.dictBind).strip().split(',')
        cmd = stmt.strip().lower()        
        logger.debug('stmt=%s, args=%s' % (stmt, args))
        
        if  cmd == 'commit':
            self.connection.commit()
            self.lastStmt='COMMIT' 
            return failure,err
        if  cmd == 'rollback':
            self.connection.rollback() 
            self.lastStmt='ROLLBACK' 
            return failure,err
         
        try:
            ret=''
            selectStmt=False
            self.lastStmt='OTHER'
            found = self.regexp_select.matcher(stmt)
            if found.find():
                selectStmt=True
                self.cursor.execute(stmt)
            else: 
                self.cursor.execute(stmt,args)
            if selectStmt:
                ret=str(self.cursor.fetchone()[0])
                print 'ret=%s' % (ret)
                self.dictBind[args[0]] = ret
                
            return False,ret
        except Exception, e:
            err=str(e)
            #logger.error(err)
            return True, err
    
    def sendData(self, **args):
        failed,ret_message=(False,None)
        liResp = {}
        liResp['httpStatCode'] = '200'
        liResp['httpRespText'] = ''
        liResp['message']   = ''
        liResp['errorCode'] = '200'
        lines=args['data']
        logger.debug(str(lines))
        logger.debug(str(type(lines)))
        for line in lines:
            found = self.regexp_comment.matcher(line)
            if found.find():
                continue
            err, msg = self.executeSQL( line)
            if err:
                logger.error(msg)

        return liResp       
