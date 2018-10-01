#!/usr/bin/python
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from SocketServer import ThreadingMixIn

from threading import Thread

from datetime import datetime
from itertools import groupby
from xml.sax.saxutils import escape, quoteattr
import os,sys
import socket
import time
import uuid
# import generateTestReport
import xml.etree.cElementTree as et
from optparse import OptionParser
from time import gmtime, strftime

import logging
from logging import handlers
log = logging.getLogger(__name__)
logfilename  = "./logs/execReport.log"

# Limitation:
# - Cannot run the same scenario in the same campaign
# -

def id_generator():
    '''       Return a function which is a id generator    '''
    i = [0]
    def _incr():
        i[0] += 1
        return i[0]
    return _incr

def indent(elem, level=0):
    '''       Return a pretty print  ElementTree   
                input : elem = ElementTree Node as '''
    i = "\n" + level*"  "
    j = "\n" + (level-1)*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = j
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = j
    return elem        

run_id_generator = id_generator()
failure_seq_generator = id_generator()
runs = dict()
props = dict()
test_results = list()
scenarios = list()

# ======================================================================================================
class TestResult(object):
    def __init__(self, _run, _scenario, _step, _has_succeeded, _why, _context=''):
        self.id = failure_seq_generator()
        self.uid = str(uuid.uuid4())
        self.run = _run
        self.scenario = _scenario
        self.step = _step
        self.has_succeeded = _has_succeeded
        self.why = _why
        self.context = _context

    def simple_repr(self):
        data = ['id', 'step']
        for i in data: yield ("%s:%s" % (i, self.__dict__[i]))

    def xml_representation(self):
        for i in data: yield (escape("<%s>%s</%s>" % (i, self.__dict__[i], i)))
        
    def element_tree(self):
        log.debug("TestResult.element_tree")
        (eid, ename, estatus) =  (escape(str(self.id)), escape(self.step), escape(self.has_succeeded) )
        element =  et.Element("testcase",{ "id"     : eid, 
                                           "name"   : ename , 
                                           "status" : estatus
                                         }
                             )
        # log.debug("\r\n\t\tcontext : {}\r\n\t\tmsg : {}".format(escape(self.context),escape(self.why)))
        et.SubElement(element, "message", {"context" : escape(self.context)}).text = escape(self.why)
        log.debug("element : {}".format( et.tostring(element)))
        return element
                                                    
        
    def junit_representation(self):
        result = ""
        if self.has_succeeded == "success":
            result = '\t\t<testcase classname=%s name=%s/>\n' % (quoteattr(self.step), quoteattr(self.uid))
        else:
            result = '\t\t<testcase classname=%s name=%s>\n' % (quoteattr(self.step), quoteattr(self.uid))
            result += ('\t\t\t<failure type="grinder" message=%s>%s</failure>\n' % (quoteattr(self.why), escape(self.context)))
            result += '\t\t</testcase>\n'
        return result

# ======================================================================================================
class MyFuncs(object):
    def __init__(self,output = "grinder_test_results.xml"):
        self.current_run = 0
        self.current_scenario = None
        self.outputFile = output

    def ping(self, arg):
        return 0

    def log_test_result(self, h):
        log.info('{CR} new test result incoming {CR}'.format(CR='*'*15))
        # test_result = TestResult(self.current_run, h['scenario'], h['stepname'], h['state'], h['why'], h['context'])
        test_result = TestResult(self.current_run, h['scenario'], h['stepname'], h['state'], h['why'])
        test_results.append(test_result)

        for i in h: log.info("{} -> {}".format(i, h[i] ))
        return test_result.uid

    def start_run(self, arg):
        '''
          Start of a new test plan = a new functional run
        '''
        ## Reset test result
        self.reset_result()
        ##
        r = run_id_generator()
        runs[r] = datetime.utcnow()
        props[r] = arg
        log.info("Start run %s" % r)
        self.current_run = r
        return r

    def end_run(self, arg):
        log.info( "End run")
        cwd = os.getcwd()
        # self.write_all_results_to_xml_file(cwd + "/grinder_test_results.xml")
        self.write_all_results_to_xml_file(self.outputFile)
        
        return 0

    #################
    def start_scenario(self, infile):
        log.info( "Start scenario %s" % infile)
        scenarios.append(infile)
        self.current_scenario = infile
        return 0

    #################
    def end_scenario(self, arg):
        log.info( "End scenario %s" % self.current_scenario)
        return 0

    #################
    def filter_run(self,lst, _id):
        '''
          return a complete run
        :param lst: a list of failures
        :param _id: a run id (run id is an identification of a functional run)
        '''
        for i in lst:
            if i.run == _id: yield i

    #################
    def filter_scenario(self,lst, _id):
        '''
          return a complete run
        :param lst: a list of failures
        :param _id: a run id (run id is an identification of a functional run)
        '''
        for i in lst:
            if i.scenario == _id: yield i

    #################
    def conditional_count(self,test_suite, f):
        return (sum(1 if f(x) else 0 for x in test_suite))


    #################
    def write_all_results_to_xml_file(self,result_file_name):
        log.info( "************* write_all_results_to_xml_file: %s ******************************" % result_file_name)
        try:
            all_test_suites = et.Element("testsuites")
            # log.debug( "xx all_test_suites :{dump}".format(dump = et.tostring(all_test_suites)))
            for run_id in runs:
                test_suites = groupby([i for i in self.filter_run(test_results, run_id)], lambda x: x.scenario.split('.')[0])
                log.debug( "** run_id :{}".format( run_id ))
                for test_suite_name, test_suite_properties in test_suites:
                    single_test_suite = list(test_suite_properties)
                    xtest_suite = et.SubElement(all_test_suites, "testsuite", {
                                                        'name'     : test_suite_name,
                                                        'tests'    : str(len(single_test_suite)),
                                                        'failures' : str(self.conditional_count(single_test_suite,lambda x:x.has_succeeded=="failed")),
                                                        'run_id'   : str(run_id)
                                                }
                                                )
                    log.debug( "xx xtest_suites :{}".format( et.tostring(all_test_suites)))
                    for test_in_current_suite in single_test_suite:
                        xml_test = test_in_current_suite.element_tree()
                        xtest_suite.append(xml_test)
                        
            indent(all_test_suites)
            log.debug( "xx all_test_suites :{}".format( et.tostring(all_test_suites)))
            outputFileName = "{}_{}.{}".format(os.path.splitext(result_file_name)[0] ,strftime("%Y-%m-%d_%H-%M-%S", gmtime()),"xml")
            log.debug( "**outputFileName :{}".format(outputFileName))
            et.ElementTree(all_test_suites).write(outputFileName, encoding='utf-8', xml_declaration=True, default_namespace=None, method="xml")
            log.debug( "** () / {} writen".format( os.getcwd(),outputFileName ))
            et.ElementTree(all_test_suites).write(result_file_name, encoding='utf-8', xml_declaration=True, default_namespace=None, method="xml")
            log.debug("{} and {} report created".format(outputFileName,result_file_name))           
            
        except Exception,e:
            log.error('error while writing output: {}'.format(e))
            raise e
            
        return result_file_name

    #################
    def write_all_results_to_xml_file_all_in_one_test_suites(self,result_file_name):
        log.info( "************* write_all_results_to_xml_file: %s ******************************" % result_file_name)
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")

        test_suites  = groupby(test_results, lambda x: x.scenario.split('.')[0])
        test_suites1 = groupby(test_results, lambda x: x.scenario.split('.')[0])
        length = sum(1 for x in test_suites1)
        test_suites2 = groupby(test_results, lambda x: x.scenario.split('.')[0])

        failures_number = 0
        for test_suite_name, test_suite_properties in test_suites2:
           single_test_suite = list(test_suite_properties)
           for test_in_current_suite in single_test_suite:
              if test_in_current_suite.has_succeeded == "failed":
                  failures_number += 1
                  break;

        result_file.write("\t<testsuite name=\"%s\" tests=\"%s\" failures=\"%s\" >\n" % ("GRINDER_CAMPAIGN", length, failures_number))

        #self.conditional_count(test_suites2,(lambda y: self.conditional_count(y,lambda x:x=="failed")))));
        for test_suite_name, test_suite_properties in test_suites:
          single_test_suite = list(test_suite_properties)

          result = '\t\t<testcase classname=%s name=%s' % (quoteattr(test_suite_name), quoteattr(test_suite_name))

          for test_in_current_suite in single_test_suite:
              if test_in_current_suite.has_succeeded == "failed":
                  result += '>\n'
                  result += ('\t\t\t<failure type="grinder" message=%s>%s</failure>\n' % (quoteattr(test_in_current_suite.why), escape(test_in_current_suite.context)))
                  result += '\t\t</testcase>\n'
                  # Hypothesis there is only one failed in a scenario
                  break;
          else:
              result += "/>\n";

          result_file.write(result)
        result_file.write("\t</testsuite>\n")
        result_file.write("</testsuites>\n")
        result_file.close()
        return result_file_name

    def write_results_to_xml_file(self, run_id, result_file_name):
        test_suites = groupby([i for i in self.filter_run(test_results, run_id)], lambda x: x.scenario)
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")
        for test_suite_name, test_suite_properties in test_suites:

            single_test_suite = list(test_suite_properties)
            result_file.write("\t<testsuite tests=\"%s\" failures=\"%s\" >\n" % (len(single_test_suite), self.conditional_count(single_test_suite,lambda x:x.has_succeeded=="failed")))
            for test_in_current_suite in single_test_suite:
                result_file.write(test_in_current_suite.junit_representation())

            result_file.write("\t</testsuite>\n")

        result_file.write("</testsuites>\n")
        result_file.close()
        return result_file_name

    def write_results_nice (self,run_id,suite,result_file_name):
        test_suites = groupby([i for i in self.filter_run(test_results, run_id)], lambda x: x.scenario)
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<tests>\n")
        for test_suite_name, test_suite_properties in test_suites:

            single_test_suite = list(test_suite_properties)
            outcome = "FAILED" if (any ((x.has_succeeded=="failed") for x in single_test_suite))  else "PASSED"
            result_file.write("\t<test name= \"%s\" suite=\"%s\" result=\"%s\">" %  (escape (test_suite_name), escape(suite), escape(outcome)))


            result_file.write("\t</test>\n")

        result_file.write("</tests>\n")
        result_file.close()
        return result_file_name

    def write_results_to_custom_file(self, run_id, fname):
        h = groupby([i for i in self.filter_run(test_results, run_id)], lambda x: x.scenario)
        f = open(fname, 'w')
        for key, group in h:
            f.write("scenario: %s\n" % key)
            for j in group:
                f.write('\t')
                f.write(",".join([k for k in j.simple_repr()]))
                f.write("\n")
        f.close()
        return fname

    def diff_steps(self, prev_id, next_id):
        prev_failures = [(f.scenario, f.step) for f in self.filter_run(test_results, prev_id)]
        next_failures = [(f.scenario, f.step) for f in self.filter_run(test_results, next_id)]
        log.debug( prev_failures)
        log.debug( next_failures)
        return [i for i in (set(next_failures) - set(prev_failures))]

    def diff_scenario(self, prev_id, next_id):
        prev_failures = [key for key, group in
                         groupby([i for i in self.filter_run(test_results, prev_id)], lambda x: x.scenario)]
        next_failures = [key for key, group in
                         groupby([i for i in self.filter_run(test_results, next_id)], lambda x: x.scenario)]
        log.debug( prev_failures)
        log.debug( next_failures)
        return [i for i in (set(next_failures) - set(prev_failures))]

    def report(self, run):
        pass

    def reset_result(self):
        log.info( '************* reset_result ******************************')
        runs.clear()
        props.clear()
        del test_results[:]
        del scenarios[:]
        self.current_run = 0
        self.current_scenario = None
        return 0

    def stop(self):
        # global quit
        server.shutdown()
        return 0

# ======================================================================================================
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


# ======================================================================================================
class LogServer(Thread):
    def __init__(self, ip, port,uri,output):
        super(LogServer, self).__init__()
        self.running = True
        rpc_paths = ('/RPC2',)
        # print ("impleXMLRPCServer({})..").format(iptuple)
        self.server = SimpleXMLRPCServer((ip, port),requestHandler=RequestHandler)
        self.server.register_introspection_functions()
        self.outputfile = output
        self.server.register_instance(MyFuncs(self.outputfile))

    def register_function(self, function):
        log.info( "%s\r\nLogServer started".format("="*30,))
        self.server.register_function(function)

    def run(self):
        self.server.serve_forever()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        
# ======================================================================================================
def generatehtml():
    # not used yet
    # h = HTML()
    pass

def main():
    fileOut     = "TestResults.xml"
    server_host = "sadcsim5mon1"
    server_port = 8000
    uri="/RPC2"

    parser = OptionParser()
    parser.add_option("-u", "--url",   dest="c_ip",   default = server_host,
                      help="colector url      default : {}".format(server_host))
    parser.add_option("-p", "--port ", type="int", dest="c_port", default = server_port,
                      help="colector port    default : {}".format(server_port))
    parser.add_option("-f", "--fileOut ", dest="fileOut", default = fileOut,
                      help="result File      default : '{}'".format(fileOut))
    
    (options, args) = parser.parse_args()
    # print ("options : ip : {}, port : {}".format(options.c_ip,options.c_port))

    server_host = options.c_ip
    server_port = options.c_port
    fileOut     = options.fileOut
    loglevel  = logging.DEBUG
    consloglevel = logging.DEBUG

    logformat = '%(asctime)s - %(funcName)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=logformat,level=consloglevel,stream=sys.stdout)
    log.debug(("logfilename:{}".format(logfilename)))
    filelog = handlers.RotatingFileHandler(logfilename,maxBytes=1048576, backupCount=2)
    filelog.setLevel(loglevel)
    filelogformat = logging.Formatter('%(asctime)s : %(message)s')
    filelog.setFormatter(filelogformat)
    logging.getLogger("").addHandler(filelog)
    
    ################
    log.info( "{} START LOG SERVER {}".format("+"*23,"+"*24)                                                     )
    log.info( "Log Server started http://{}:{}{}".format(server_host,str(server_port),uri)                       )
    log.info( "   - In your grinder properties file be sure to have :"                                           )
    log.info( "          grindertool.custom.logger.activate=True"                                                )
    log.info( "          grindertool.custom.logger.url=http://{}:{}{}".format(server_host,str(server_port),uri)  )
    log.info( "   Run your campaign"                                                                             )
    log.info( "   The file is generated at the end of the Campaign to {}".format (fileOut)                       )
    log.info( "   The log file is generated in  {}".format (logfilename)                                         )

    log.debug(("starting server"))
    mlogServer = LogServer(server_host, server_port, uri, fileOut)
    mlogServer.start()


if __name__ == '__main__' :
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    main()
