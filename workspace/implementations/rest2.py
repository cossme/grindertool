"""
    Author      : O.Merlin
    Date        : 29/11/2017
    Description : Rest implementation without template usage for performance 
"""
import base64
from corelibs.coreGrinder import CoreGrinder
from rest import rest
from net.grinder.plugin.http import HTTPPluginControl

logger=CoreGrinder.getLogger()
properties=CoreGrinder.getProperty()


class rest2(rest):

    def __init__(self, _dataFilePath, _templateFilePath):    
        rest.__init__(self, _dataFilePath, _templateFilePath)  
       
    def version(self):
        return '0.2'                
        
    def formatHeaders(self, args):
        """
            Transform String headers to a dictionary of headers
        :param args:
        """
        if 'rest_request_headers' not in args['data']:
            return dict()

        if isinstance(args['data']['rest_request_headers'], basestring):
            # logger.debug('%s - rest_request_header type=basestring - [value="%s"]' % (self.__class__.__name__, args['data']['rest_request_headers']))
            _list = args['data']['rest_request_headers'].split('|')

            # Transform the list into a dictionary
            _headers = dict([(k.split(':', 1)[0].strip(), k.split(':', 1)[1].strip()) for k in _list])

        elif isinstance(args['data']['rest_request_headers'], dict):
            # logger.debug('%s - rest_request_header type=basestring - [value="%s"]' % (self.__class__.__name__, args['data']['rest_request_headers']))
            _headers = args['data']['rest_request_headers']
        else:
            raise SyntaxError('"rest_request_headers" must be of type "basestring" or "dictionary"')

        # If nothing add Json Content-Type
        if 'Content-Type' not in _headers:
            _headers['Content-Type']='application/json'

        return _headers
        
    def sendData(self, **args):
        """
          A more efficient way to call Http rest without any templating String
        """
        logger.debug('%s - sendData called.' % self.__class__.__name__)
        
        if not 'rest_request_uri' in args['data']:
            logger.error('%s.sendData - missing a missing parameter "rest_request_uri"' (self.__class__.__name__))
            raise NotImplementedError('%s.sendData - missing a missing parameter "rest_request_uri"' (self.__class__.__name__))
                
        # Headers
        headers = self.formatHeaders(args)
            
        # Basic authentication Header
        if ('rest_basic_auth_user' and  'rest_basic_auth_password') in args['data']:
            HTTPPluginControl.getConnectionDefaults().setUseCookies(0)
            headers['Authorization']='Basic %s' % (base64.b64encode('%s:%s' % (args['data']['rest_basic_auth_user'],
                                                                               args['data']['rest_basic_auth_password'])))

        # Body
        body=args['data'].get('rest_request_body', None)
        method=args['data'].get('rest_request_method', 'POST' if body else 'GET')
                
        # Call Http implementation
        liResp=self.sendSimpleHTTP(uri=args['data'].get('rest_request_uri'),  
                                   body=body,
                                   headers=headers,
                                   method=method, 
                                   reporter=args['reporter'],
                                   testname=args['testname'])
                
        HTTPPluginControl.getConnectionDefaults().setUseCookies(1)

        liResp=self.processJSONResponse(liResp)
                    
        return liResp
