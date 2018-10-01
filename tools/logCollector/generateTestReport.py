import xmlrpclib
import os,sys
import argparse

    
class collector_instance:

    def __init__(self, url, tracefile='./logtrace.txt'):
        print "connecting proxy %s" %(url,)
        print("="*20)        
        self.collector = xmlrpclib.ServerProxy(url)
        self.tracefh =  open(tracefile, 'w')

    def log_test_result(self, *args, **kwargs):
        self.tracefh.write ("\n")
        for k in kwargs:
            self.tracefh.write("%s -> %s\n" % (k, kwargs[k] ))
        result_id = self.collector.log_test_result(dict((k, v) for k, v in kwargs.iteritems() if v))
        return result_id

    def __getattr__(self, name):
        return self.collector.__getattr__(name)
            
class collectorReport:

    def __init__(self, url='http://127.0.0.1:8000/RPC2', tracefile='./logtrace.txt'):
        self.proxy=collector_instance(url)

    def generareReport(self,fileout = "TestResults.xml",testCase = "TestCase"):
        try:
            out_f, out_ext = os.path.splitext(fileout)
            # def write_results_nice (self,run_id,suite,result_file_name):
            print "%s start report 1 :%s_1%s"%("*"*30, out_f,out_ext)
            self.proxy.write_results_nice(1,testCase,"%s_1%s" %(out_f,out_ext))
            # def write_results_to_xml_file(self, run_id, result_file_name):
            print "%s start report 2 :%s_2%s"%("*"*30, out_f,out_ext)
            self.proxy.write_all_results_to_xml_file("%s_2%s" %(out_f,out_ext))
            print "%s start report 3 :%s_3%s"%("*"*30, out_f,out_ext)
            self.proxy.write_all_results_to_xml_file1("%s_3%s" %(out_f,out_ext))
            # self.proxy.write_all_results_to_xml_file_all_in_one_test_suites("%s_4%s" %(out_f,out_ext))
            # self.proxy.log_test_result("%s_5%s" %(out_f,out_ext))
        except Exception as err:
            print "A fault occurred"
            print "Fault code: %s" % str(err)
    
    def stopServer(self):
        self.proxy.stop()

if __name__ == "__main__":
    print "*"*30 
    parser = argparse.ArgumentParser(prog='PROG', usage='%(prog)s [options]')
    #parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'),default=sys.stdout)
    parser.add_argument("-f","--fileOut", required=False ,default="TestResults.xml")
    parser.add_argument("-u","--url", required=False ,default="http://127.0.0.1:8000/RPC2")
    args = parser.parse_args()
    print "%s\r\n%s\r\n%s\r\n" %("*"*30, str(args),"*"*30)
    # mreport = collectorReport("http://127.0.0.1:8000")
    collectorReport(args.url).generareReport(args.fileOut)
    print "*"*30