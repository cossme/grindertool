"""
"""
import base64
from java.lang import System

from net.sf.json import JSONSerializer, JSONException

from corelibs.coreGrinder import CoreGrinder
from http import http
from net.grinder.plugin.http import HTTPPluginControl


#from core import core
logger=CoreGrinder.getLogger()

class rest(http):
 
    def __init__(self,_dataFilePath, _templateFilePath):    
        http.__init__(self, _dataFilePath, _templateFilePath)

    def version(self):
        setVersion = '$Header: apache_http 1.0 2015/03/26 14:22:45CEST scrouin Exp  $'.split( )[1:3]
        return setVersion[0].split('.')[0] + ' <'+setVersion[1] +'>'

    def processJSONResponse(self, liResp):      
        '''
         retrieve the necessary data (status code, errorCode, message)
        :param liResp: 
        '''
        logger.debug("Rest implementation, process json response called.")
        
        #TODO: How to handle an empty JSON response ... is it possible ? 
        if not liResp:
            logger.error("Rest implementation, response dictionary CANNOT be NULL.")
            raise SyntaxError("Rest implementation, response dictionary CANNOT be NULL.")           

        if 'responseText' in liResp:
            response = liResp['responseText']
        else:
            logger.warn('Rest implementation, "responseText" not found')
            return liResp
         
        logger.debug('Rest implementation, process json response: response is [%s]' % (response))
        
        if response == '':
            return liResp
        
        try:
            json_response = JSONSerializer.toJSON(response)
            liResp['responseFormat'] = 'json'
        except JSONException:
            logger.debug('Response not in JSON format')
            liResp['responseFormat'] = 'txt'
            return liResp
        
        try:
            if isinstance(json_response, dict):
                
                # TODO: add a to_flattened_dictionary() 
                dict_json = dict(json_response)
                
                # check errorCode key hardcoded in response 
                if 'errorCode' in dict_json:
                    dict_json['jsonErrorCode']=dict_json['errorCode']
                    dict_json['errorCode'] = -1
                    if 'errorCode' in liResp:
                        dict_json['errorCode'] = liResp['errorCode']

                # add all Json keys
                liResp.update(dict_json)
                        
        except ValueError, e:
            logger.error('Reason: "%s", response="%s"' % (e, json_response))

        # Unmodified JsonResponse for complex assertion
        liResp.update({'rawJsonResponse': json_response})

        logger.trace("liResp returned is [%s]" % liResp)
        return liResp       

    def sendData(self, **args):
        '''
         should get all inputs from step/scenario and generate 
         request0 and response0 keys in data just like when we have templates
         but without templates
        '''
        use_reporter=False
        if 'reporter' in args and args['reporter']:
            use_reporter=True
        
        logger.debug("Rest implementation, sendData called.")
        
        # consider we are in legacy mode with something like "request0.uri= ...."
        if isinstance(args['data'], basestring): 
            if logger.isDebugEnabled():
                logger.debug("Rest implementation, sendData called with legacy request data in string format [%s]" % (args['data']))
            if logger.isInfoEnabled():
                logger.info("%s data   sent  is [%s]" % (self.__class__.__name__, args['data']))
            li_resp = self.sendHTTP(args['data'])
            if logger.isInfoEnabled():
                logger.info("%s li_resp returned is [%s]" % (self.__class__.__name__, li_resp))
            
            return self.processJSONResponse(li_resp)

        # -------------------------------------------
        logger.debug("Rest implementation, sendData called without legacy request data in string format.")
        data=args['data']
        if 'rest_request_uri' not in data:
            logger.error('%s.sendData - missing parameter "rest_request_uri"' % self.__class__.__name__)
            raise NotImplementedError('%s.sendData - missing parameter "rest_request_uri"' % self.__class__.__name__)
        if 'rest_request_body' not in data:
            logger.error('%s.sendData - missing parameter "rest_request_body"' % self.__class__.__name__)
            raise NotImplementedError('%s.sendData - missing parameter "rest_request_body"' % self.__class__.__name__)

        rest_request_uri=data.get('rest_request_uri')
        rest_request_body=data.get('rest_request_body')

        ### Headers
        rest_request_headers=data.get('rest_request_headers', 'Content-Type:application/json') 
        # Transform the headers list into the headers string format ( "|" delimiter )
        if isinstance(rest_request_headers, list):
            rest_request_headers='|'.join(rest_request_headers)

        ### Basic authentication Header
        basicAuthentStr=''
        if 'rest_basic_auth_user' in data and 'rest_basic_auth_password' in data:
            basicAuthentStr = 'Authorization: Basic %s' % (base64.b64encode('%s:%s' % (data['rest_basic_auth_user'],data['rest_basic_auth_password'])))+'|'
            HTTPPluginControl.getConnectionDefaults().setUseCookies(0)
        rest_request_headers+= '|%s' % basicAuthentStr if basicAuthentStr else ''
        
        logger.debug("Rest implementation, sendData formatting request data for http implementation.")
        send_http_str2send = ('request0.headers=%s\nrequest0.uri=%s\nrequest0.body=%s\nrequest0.method=%s\nresponse0.statuscode=%s') % (rest_request_headers,
                                rest_request_uri,rest_request_body,
                                data.get('rest_request_method','POST' ),
                                data.get('rest_response_status_code', '200' ))

        logger.debug("Rest implementation, sendData sending http [%s]" % (send_http_str2send))

        # check reporter
        if 'reporter' in args and args['reporter']:
            # Low overhead call (minimum processing)
            start_time = System.currentTimeMillis()
            try:
                li_resp=self.sendHTTP(send_http_str2send)
            finally:
                try:
                    delta_time = System.currentTimeMillis() - start_time
                    args['reporter'].setTime2(delta_time, args['testname'])
                    if logger.isTraceEnabled():
                        logger.trace('Test "%s" execution time : %d' % (args['testname'], delta_time))
                    li_resp['grindertool.step.executionTime'] = delta_time
                finally:
                    logger.warn('%s - Measurement error on sendHTTP call' % self.__class__.__name__)
        else:
            li_resp=self.sendHTTP(send_http_str2send)

        HTTPPluginControl.getConnectionDefaults().setUseCookies(1)

        logger.debug("Rest implementation, sendData processing response [%s]" % (li_resp))
        li_resp=self.processJSONResponse(li_resp)
               
        logger.debug("Rest implementation, sendData return response [%s]" % (li_resp))
        
        return li_resp
           


