'''
Created on 29 sept. 2014

@author: omerlin
'''

from java.io import IOException
from java.lang import Exception as JavaException

from org.apache.http import HttpHost
from org.apache.http.client.methods import HttpPost, HttpGet
from org.apache.http.conn.routing import HttpRoute
from org.apache.http.entity import StringEntity
from org.apache.http.impl.client import  HttpClients
from org.apache.http.impl.conn import PoolingHttpClientConnectionManager

from corelibs.coreGrinder  import CoreGrinder
logger=CoreGrinder.getLogger()

# http://hc.apache.org/httpcomponents-client-ga/tutorial/html/connmgmt.html
class ContextRouterClient:
    
    httpClient=None
    
    def __init__(self, host,port):
        self.uri_create='http://%s:%s/context/create' % (host,port)
        self.uri_createBatch='http://%s:%s/context/createBatch' % (host,port)
        self.uri_delete='http://%s:%s/context/delete' % (host,port)
        self.uri_ping='http://%s:%s/context/ping' % (host,port)
        cm = PoolingHttpClientConnectionManager()
        # Increase max total connection to 200
        cm.setMaxTotal(200)
        # Increase default max connection per route to 20
        try:
            routerhost = HttpHost(host, port)
        except Exception, ex:
            logger.error( 'ContextRouterClient error - [host=%s][port=%d], exception=%s' % (host,port,ex))
            raise Exception('ContextRouterClient error - [host=%s][port=%d], exception=%s' % (host,port,ex))
        cm.setMaxPerRoute(HttpRoute(routerhost), 100)
        
        self.__class__.httpClient = HttpClients.custom().setConnectionManager(cm).build()

    def getCreateUri(self):
        return self.uri_create
    def getCreateBatchUri(self):
        return self.uri_createBatch

    def getDeleteUri(self):
        return self.uri_delete
    
    def ping(self):
        httpGet = HttpGet(self.uri_ping)
        try:
            response = self.__class__.httpClient.execute(httpGet)
        except JavaException,e:
            logger.error('>>>>>>>>>>>httpClient ping error on %s <<<<<<<<<<<<<<<<<< ' % (self.uri_ping))
            raise Exception(e)
                 
        res_code = response.getStatusLine().getStatusCode()

        if res_code!=200:
            logger.error('ping - Error calling "%s" ' % (self.uri_ping))
            raise Exception('ping - Error calling "%s" ' % (self.uri_ping))
   
    def postJsonMessage(self, jsonMessage, uri):
            httpPost = HttpPost(uri)
            httpPost.addHeader("Content-Type", "application/json")
            response=None
            try:
                httpPost.setEntity(StringEntity(jsonMessage, "UTF-8"))
                
                try:
                    response = self.__class__.httpClient.execute(httpPost)
                except JavaException,e:
                    logger.error('>>>>>>>>>>>httpClient.execute error <<<<<<<<<<<<<<<<<< ')
                    raise Exception(e)
                
                res_code = response.getStatusLine().getStatusCode()

                if res_code!=200:
                    logger.error('postJsonMessage - Error calling "%s" with content "%s"' % (uri, jsonMessage))
                    raise Exception('postJsonMessage - Error calling "%s" with content "%s"' % (uri, jsonMessage))
                    
            except JavaException, e:
                logger.error( "postJsonMessage - Http call failed, \ntrace: %s" %  (e))
                raise Exception('postJsonMessage - Http call failed, \ntrace: %s' %  (e))

            finally:
                if response:
                    response.close()