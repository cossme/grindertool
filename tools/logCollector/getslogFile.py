#!/usr/bin/python
# -*- coding: utf-8 -*-
#File string input format: file in: "C:\NR\logs\85S4SY1-3.log"  -- write with quotes

import re

fi=r"C:\NR\logs\85S4SY1-1.log"
fo=r"C:\NR\logs\85S4SY1-1_OUT.log"

s = "state=StopStep"


def filter(txt, inputfile, newfile):
    '''\
    write the in a file the lines of the input file where a string is 
    '''
    list = ["date", "debug", "uid", "state", "status", "cause", "test", "async", "step", "testid", "scenario", "scenarioId"]
    p=re.compile("(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (?P<debug>\w+).*uid=(?P<uid>\d+).*state=(?P<state>\w+).*status=(?P<status>\w+).*cause=(?P<cause>.*)\]\[test=(?P<test>.*)\]\[async=(?P<async>\w+).*\]\[step=(?P<step>\d+).*\]\[testid=(?P<testid>\d+).*\]\[scenario=(?P<scenario>.*)\]\[scenarioId=(?P<scenarioId>\d+)")
    with open(newfile, 'w') as outfile, open(inputfile, 'r') as infile:
        lo='\t'.join(list) + '\n'
        outfile.write(lo)
        for line in infile:
            if s in line :
                m=p.search(line)
                lo="\t".join(m.groups())
                outfile.write("%s\n" %(lo))

fi = input('file in: ')  
fo = fi +".res"  


print "reading "+fi +" -------------" 
res = filter(s,fi,fo)

print "writing "+fo+"-------------"

print "End -------------"
