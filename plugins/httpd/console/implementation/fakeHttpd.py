import SocketServer 
import BaseHTTPServer
import SimpleHTTPServer
import urlparse

def responseGenerator(c):
    for i in range(0,c):
        res = dict()
        res['text']=str(i)
        yield res
    return

def ok_responseGenerator(c):
    for i in range(0,c):
        res = dict()
        res['status']=200
        res['cont_type']='Text/Plain'
        res['text']='OK'      
        yield res
    return

serverConf = dict()

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
	parsed_path = urlparse.urlparse(self.path)
	message_parts = [
        '<COMMAND>%s</COMMAND>' % self.command,
        '<URL>%s</URL>' % parsed_path.path,
        '<PARAMS>%s</PARAMS>' % parsed_path.query
        ]
	for name, value in sorted(self.headers.items()):
           message_parts.append('<%s>%s</%s>' % (name, value.rstrip(),name))
        message = '\n'.join(message_parts)
        #print message
        RequestHandler.lastRequest = message
        self.send_response(RequestHandler.res['status'])
	self.send_header("Content-type:", RequestHandler.res['cont_type'])
	self.send_header("Content-Length:", len(RequestHandler.res['text']))
	self.end_headers()
	self.wfile.write(RequestHandler.res['text'])
    
    def do_POST(self):
        parsed_path = urlparse.urlparse(self.path)
        length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(length).decode('utf-8')
        RequestHandler.lastRequest = str(post_data)
        self.send_response(RequestHandler.res['status'])
	self.send_header("Content-type:", RequestHandler.res['cont_type'])
	self.send_header("Content-Length:", len(RequestHandler.res['text']))
	self.end_headers()
	self.wfile.write(RequestHandler.res['text'])

    def log_message(self, format, *args):
        print "Got request!"
        return
        
        
class CustomHTTPServer(BaseHTTPServer.HTTPServer):
    def server_bind(self):
        BaseHTTPServer.HTTPServer.server_bind(self)
        print "Service bound!\n"
        self.socket.settimeout(serverConf['timeout'])
        self.is_timeout=0

    def handle_timeout(self):
        print "Timeout!"
        self.is_timeout=1

def wait_for_request (port, body, status, cont_type, timeout):
    serverConf['timeout'] = timeout
    server = CustomHTTPServer(('',port), RequestHandler)
    mock_request = dict()
    mock_request['status']=status
    mock_request['cont_type']=cont_type
    mock_request['text']=body
    RequestHandler.res = mock_request
    server.handle_request()
    return getattr(RequestHandler, 'lastRequest', None)
    

#if __name__ == '__main__':
#	print "Starting server\n"
#	server = CustomHTTPServer(('localhost',8000), RequestHandler)
#        for i in ok_responseGenerator(50):
#            RequestHandler.res = i
#            server.handle_request()
#          
#	print "Ending server"
