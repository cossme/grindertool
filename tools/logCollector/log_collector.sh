#!/bin/bash
#====================================================================
# deduce current location from this script
scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"
filename=`basename $0`

cd $scriptPath
SCRIPT="log_collector.py"
USR=`whoami`
#====================================================================
## Params :
HOST=`hostname`
#COLLECTOR_HOST=`grep ${HOST} /etc/hosts |awk '{print $1}' |head -1`
COLLECTOR_HOST=${HOST}
COLLECTOR_PORT="8000"
LOG_CONSOLE="${scriptPath}/logs/ExecutionConsole.log"
REPORT="${scriptPath}/report/TestResults.xml"
#====================================================================
#Path  and classPath
PROJECTDIR=`cd $scriptPath/.. && /bin/pwd`
REPORTDIR="./"

#CP="${JYTHONPATH}/jython-standalone-2.7.0.jar"

if [ ! -z "$CLASSPATH" ]
then
  CP=$CP:$CLASSPATH
fi
#====================================================================

start() {
	PARAM="-u ${COLLECTOR_HOST} -p ${COLLECTOR_PORT} -f ${REPORT}"
	cmd="python  ${REPORTDIR}/${SCRIPT} ${PARAM}"

	echo "=== Start Log Collector"
	echo "cmd : ${cmd}"
	echo "log in $LOG_CONSOLE"
	nohup ${cmd} >$LOG_CONSOLE 2>&1 &
	echo "======================="
	#====================================================================
	# Java version
	# PARAM=""
	#cmd="${JAVA_HOME}/bin/java -classpath ${CP} org.python.util.jython  ${REPORTDIR}/log_collector.py ${PARAM}"
	# for only python
	#====================================================================
	# tail -f $LOG_CONSOLE
}

kill_cmd() {
    SIGNAL=""; MSG="Killing "
    while true
    do
        LIST=`ps -ef | grep -v grep | grep $SCRIPT | grep -w $USR | awk '{print $2}'`
        if [ "$LIST" ]
        then
            echo; echo "$MSG $LIST" ; echo
            echo $LIST | xargs kill $SIGNAL
            sleep 2
            SIGNAL="-9" ; MSG="Killing $SIGNAL"
        else
           echo; echo "All killed..." ; echo
           break
        fi
    done
}

stop() {
	
    echo "==== Stop"
    echo "$(date '+%Y-%m-%d %X'): STOP" >>$LOG_CONSOLE
	kill_cmd
}

status() {
    echo
    echo "==== Status"

	echo "===== list $SCRIPT "
	for i in `ps -ef|grep -i $SCRIPT| grep -v $filename|grep -v grep|awk '{print $2}'`
	do
	   echo ">>> $i"
	   echo "status: " $(ps -ef|grep $i |grep -v grep)
	   #|awk '{print $1,$2,$9,$10,$11,$12,$13,$14,$15}')
	done
	echo "===== All $SCRIPT listed"
	
}


case "$1" in
    'start')
            start
			status
            ;;
    'stop')
            stop
            ;;
    'restart')
            stop ; echo "Sleeping..."; sleep 1 ;
            start
			status
            ;;
    'status')
            status
            ;;
    *)
            echo
            echo "Usage: $0 { start | stop | restart | status }"
            echo
            exit 1
            ;;
esac

exit 0
