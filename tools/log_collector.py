#!/usr/bin/python
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from datetime import datetime
from itertools import groupby
from xml.sax.saxutils import escape, quoteattr
import os
import socket
from time import strftime, gmtime
import uuid

# Limitation:
# - Cannot run the same scenario in the same campaign
# -


def id_generator():
    """
       Return a function which is a id generator
    """
    i = [0]

    def _incr():
        i[0] += 1
        return i[0]

    return _incr


run_id_generator = id_generator()
failure_seq_generator = id_generator()
runs = dict()
props = dict()
test_results = list()
scenarios = list()


def filter_run(lst, _id):
    """
      return a complete run
    :param lst: a list of failures
    :param _id: a run id (run id is an identification of a functional run)
    """
    for i in lst:
        if i.run == _id:
            yield i


def filter_scenario(lst, _id):
    """
      return a complete run
    :param lst: a list of failures
    :param _id: a run id (run id is an identification of a functional run)
    """
    for i in lst:
        if i.scenario == _id:
            yield i


def conditional_count(test_suite, f):
    return sum(1 if f(x) else 0 for x in test_suite)


class TestResult:
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
        for i in data:
            yield ("%s:%s" % (i, self.__dict__[i]))

    def xml_representation(self):
        data = ['id', 'step', 'has_succeeded']
        for i in data:
            yield (escape("<%s>%s</%s>" % (i, self.__dict__[i], i)))

    def junit_representation(self):
        if self.has_succeeded == "success":
            result = '\t\t<testcase classname=%s name=%s/>\n' % (quoteattr(self.step), quoteattr(self.uid))
        else:
            result = '\t\t<testcase classname=%s name=%s>\n' % (quoteattr(self.step), quoteattr(self.uid))
            result += ('\t\t\t<failure type="grinder" message=%s>%s</failure>\n' % (quoteattr(self.why), escape(self.context)))
            result += '\t\t</testcase>\n'
        return result

class MyFuncs:
    def __init__(self):
        self.current_run = 0
        self.current_scenario = None

    def ping(self, arg):
        return 0

    def log_test_result(self, h):
        print '************* new test result incoming ******************************'
        # test_result = TestResult(self.current_run, h['scenario'], h['stepname'], h['state'], h['why'], h['context'])
        test_result = TestResult(self.current_run, h['scenario'], h['stepname'], h['state'], h['why'])
        test_results.append(test_result)

        for i in h:
            print ("%s -> %s" % (i, h[i]))
        return test_result.uid

    def start_run(self, arg):
        '''
          Start of a new test plan = a new functional run
        '''
        r = run_id_generator()
        runs[r] = datetime.utcnow()
        props[r] = arg
        print "Start run %s" % r
        self.current_run = r
        return r

    def end_run(self, arg):
        print "End run"
        cwd = os.getcwd()
        #self.write_all_results_to_xml_file(cwd + "/current_results/grinder_test_results.xml")
        return 0

    def start_scenario(self, infile):
        print "Start scenario %s" % infile
        scenarios.append(infile)
        self.current_scenario = infile
        return 0

    def end_scenario(self, arg):
        print "End scenario %s" % self.current_scenario
        return 0

    def write_all_results_to_xml_file(self,result_file_name):
        print "************* write_all_results_to_xml_file: %s ******************************" % result_file_name
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")

        tmp = dict()
        for tests in test_results:
            tmp[tests.scenario] = "a"

        for scenario_name in tmp:
            test_suites = groupby([i for i in filter_scenario(test_results, scenario_name)], lambda x: x.scenario.split('.')[0])

            for test_suite_name, test_suite_properties in test_suites:
                single_test_suite = list(test_suite_properties)
                result_file.write("\t<testsuite name=\"%s\" tests=\"%s\" failures=\"%s\" >\n" % (test_suite_name, len(single_test_suite), conditional_count(single_test_suite,lambda x:x.has_succeeded=="failed")))
                for test_in_current_suite in single_test_suite:
                    result_file.write(test_in_current_suite.junit_representation())

             result_file.write("\t</testsuite>\n")

        result_file.write("</testsuites>\n")
        result_file.close()
        return result_file_name


    def write_all_results_to_xml_file1(self,result_file_name):
        print "************* write_all_results_to_xml_file: %s ******************************" % result_file_name
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")
        for run_id in runs:
          test_suites = groupby([i for i in filter_run(test_results, run_id)], lambda x: x.scenario.split('.')[0])

          for test_suite_name, test_suite_properties in test_suites:

            single_test_suite = list(test_suite_properties)
            result_file.write("\t<testsuite name=\"%s\" tests=\"%s\" failures=\"%s\" >\n" % (test_suite_name, len(single_test_suite), conditional_count(single_test_suite,lambda x:x.has_succeeded=="failed")))
            for test_in_current_suite in single_test_suite:
                result_file.write(test_in_current_suite.junit_representation())

            result_file.write("\t</testsuite>\n")

        result_file.write("</testsuites>\n")
        result_file.close()
        return result_file_name

    def write_all_results_to_xml_file_all_in_one_test_suites(self,result_file_name):
        print "************* write_all_results_to_xml_file: %s ******************************" % result_file_name
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")

        test_suites = groupby(test_results, lambda x: x.scenario.split('.')[0])
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

        #conditional_count(test_suites2,(lambda y: conditional_count(y,lambda x:x=="failed")))));
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
        test_suites = groupby([i for i in filter_run(test_results, run_id)], lambda x: x.scenario)
        result_file = open(result_file_name, 'w')
        result_file.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        result_file.write("<testsuites>\n")
        for test_suite_name, test_suite_properties in test_suites:

            single_test_suite = list(test_suite_properties)
            result_file.write("\t<testsuite tests=\"%s\" failures=\"%s\" >\n" % (len(single_test_suite), conditional_count(single_test_suite,lambda x:x.has_succeeded=="failed")))
            for test_in_current_suite in single_test_suite:
                result_file.write(test_in_current_suite.junit_representation())

            result_file.write("\t</testsuite>\n")

        result_file.write("</testsuites>\n")
        result_file.close()
        return result_file_name

    def write_results_nice (self,run_id,suite,result_file_name):
        test_suites = groupby([i for i in filter_run(test_results, run_id)], lambda x: x.scenario)
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
        h = groupby([i for i in filter_run(test_results, run_id)], lambda x: x.scenario)
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
        prev_failures = [(f.scenario, f.step) for f in filter_run(test_results, prev_id)]
        next_failures = [(f.scenario, f.step) for f in filter_run(test_results, next_id)]
        print prev_failures
        print next_failures
        return [i for i in (set(next_failures) - set(prev_failures))]

    def diff_scenario(self, prev_id, next_id):
        prev_failures = [key for key, group in
                         groupby([i for i in filter_run(test_results, prev_id)], lambda x: x.scenario)]
        next_failures = [key for key, group in
                         groupby([i for i in filter_run(test_results, next_id)], lambda x: x.scenario)]
        print prev_failures
        print next_failures
        return [i for i in (set(next_failures) - set(prev_failures))]

    def report(self, run):
        pass

    def reset_result(self):
        print '************* reset_result ******************************'
        runs.clear()
        props.clear()
        del test_results[:]
        del scenarios[:]
        self.current_run = 0
        self.current_scenario = None
        return 0


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)


server_host="localhost"
server_port=8000 if 'LOG_COLLECTOR_PORT' not in os.environ else int(os.environ['LOG_COLLECTOR_PORT'])
server = SimpleXMLRPCServer((server_host, server_port), requestHandler=RequestHandler, logRequests=False)
server.register_introspection_functions()

server.register_instance(MyFuncs())
print "Server started http://"+server_host+":"+str(server_port)+" /RPC2"
print "^C to kill"
server.serve_forever()


