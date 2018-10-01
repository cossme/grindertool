#!/bin/bash
#
# Usage:
#       install_grindertool
# /Usage
#

script=`basename $0`
dirname=`dirname $0`
here=`cd $dirname; pwd`

GRINDERTOOL_DIR=`dirname "${here}"`
GRINDERTOOL_CONSOLE_HOST=localhost
GRINDERTOOL_JETTY_PORT=

loglevel $script INFO

echo ""
echo "*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*"
echo "                      script $script"
echo "*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*=*"
echo ""

#==============================================================================
# Default parameters
#==============================================================================


#==============================================================================
#                    Check Prerequisites / Current context
#==============================================================================


long_list_of_my_processes()
{
                local PID
                local PWDX
                local PARGS

                case `uname -s` in
                SunOS)
                               pgrep -u `whoami` |
                               while read PID
                               do
                                               PWDX=`pwdx $PID 2>/dev/null | $AWK '{ print $2 }'`
                                               PARGS=`pargs -l $PID 2>/dev/null`
                                               if [ ! -z "$PARGS" ]; then
                                                               echo "$PID $PARGS $PWDX"
                                               fi
                               done
                               ;;
                Linux)
                               pgrep -u `whoami` |
                               while read PID
                               do
                                               PWDX=`pwdx $PID 2>/dev/null | $AWK '{ print $2 }'`
                                               PARGS=`ps -o pid,comm,args -p $PID 2>/dev/null | $AWK 'NR>1 { print }'`
                                               if [ ! -z "$PARGS" ]; then
                                                               echo "$PID $PARGS $PWDX"
                                               fi
                               done
                               ;;
                *)
                               ps -u`whoami` -o pid,comm,args,cwd | $AWK 'NF>1 { print }'
                esac
}

loop_until_match()
{
	MAX_LOOPS=$1; shift
	SLEEP_TIME=$1; shift
	PATTERN="$1"; shift
	CMD="$@"
	
	i=0
	while true
	do
		resp=`$CMD`
		case $resp in
		*${PATTERN}*)
			break
			;;
		esac
		i=$(( $i + 1 ))
		
		if [ $i -gt $MAX_LOOPS ]; then
			echo "FAILED"
			return 1
		fi
		echo "Waiting for $CMD to respond $PATTERN"
		sleep $SLEEP_TIME
	done
	
	echo "$resp"
	return 0
}

loop_while_match()
{
	MAX_LOOPS=$1; shift
	SLEEP_TIME=$1; shift
	PATTERN="$1"; shift
	CMD="$@"
	
	i=0
	while true
	do
		resp=`$CMD`
		case $resp in
		*${PATTERN}*)
			:
			;;
		*)
			break
		esac
		i=$(( $i + 1 ))
		
		if [ $i -gt $MAX_LOOPS ]; then
			echo "FAILED"
			return 1
		fi
		echo "Waiting for $CMD to respond $PATTERN"
		sleep $SLEEP_TIME
	done
	
	echo "$resp"
	return 0
}

#==============================================================================
#                        GRINDERTOOL startup
#==============================================================================

stop_agents()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/agents/stop 2>/dev/null
}

stop_grinder()
{
	resp=`stop_agents`
	log $script INFO "Stop agents and workers ($resp)"

	sleep 2
	
	CONSOLE_PID=`long_list_of_my_processes | grep "net.grinder.Console" | grep "${GRINDERTOOL_DIR}" | grep -v grep | $AWK '{ print $1 }'`

	if [ ! -z "${CONSOLE_PID}" ]; then
		echo "Killing console PID = ${CONSOLE_PID}"
		kill_pids ${CONSOLE_PID}
	fi
	
}


grinder_version()
{
	curl -X GET http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/version 2>/dev/null
}

print_properties()
{
	curl -H "Accept: application/json" -X GET http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/properties 2>/dev/null
}

agents_status()
{
	curl -H "Accept: application/json" -X GET http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/agents/status 2>/dev/null
}

files_distribute()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/files/distribute 2>/dev/null
}

files_status()
{
	curl -X GET http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/files/status 2>/dev/null
}

send_properties()
{
	PROPERTY_FILE="$1"
	
	REQUEST_DATA="{\"distributeOnStartAsk\":false,"
	REQUEST_DATA="${REQUEST_DATA}\"startWithUnsavedBuffersAsk\":false,"
	REQUEST_DATA="${REQUEST_DATA}\"resetConsoleWithProcessesAsk\":false,"
	REQUEST_DATA="${REQUEST_DATA}\"propertiesNotSetAsk\":false,"
	REQUEST_DATA="${REQUEST_DATA}\"stopProcessesAsk\":false,"
	REQUEST_DATA="${REQUEST_DATA}\"sampleInterval\":1000,"
	REQUEST_DATA="${REQUEST_DATA}\"distributionDirectory\":\"${GRINDERTOOL_DIR}/console\","
	REQUEST_DATA="${REQUEST_DATA}\"propertiesFile\":\"${PROPERTY_FILE}\"}"
	
	curl -H "Content-Type: application/json" -X PUT http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/properties -d "${REQUEST_DATA}" 2>/dev/null
}

start_workers()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/agents/start-workers 2>/dev/null
}

stop_workers()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/agents/stop-workers 2>/dev/null
}

start_recording()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/recording/start 2>/dev/null
}

stop_recording()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/recording/stop 2>/dev/null
}

clear_recording()
{
	curl -X POST http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/recording/zero 2>/dev/null
}

print_run_data()
{
	curl -X GET http://${GRINDERTOOL_CONSOLE_HOST}:${GRINDERTOOL_JETTY_PORT}/recording/data 2>/dev/null
}

launch_test()
{
	local PROPERTIES_FILE="$1"   

    #
    # Count the number of agents
    # and add the property
    #
    resp=`agents_status`
    #VAR=`curl -s -H "Accept: application/json" -X GET http://localhost:6573/agents/status`
    #
    # python and pyYaml must be installed
    #
    NbAgents=`echo $resp | python -c "import yaml,sys;doc=yaml.safe_load(sys.stdin);print len(doc)"`
    
    #
    # Adding grinder.agents to the property file
    #
    # Replace or Add string grinder.agents=XXX to the ${PROPERTIES} file
    
	resp=`send_properties ${PROPERTIES_FILE}`
	log $script INFO "Sending properties for test ($resp)"
	sleep 1

	resp=`files_distribute`
	log $script INFO "Request file distribution ($resp)"

	resp=`loop_until_match 10 5 'finished' files_status`
    
	resp=`start_workers`
	log $script INFO "Start test ($resp)"

    #
    # Here we could imagine printing regularly a status of the execution ?
    # or rely on the grafana reports ?
    #
    
}

start_grinder()
{
	resp=`loop_until_match 10 1 'The Grinder' grinder_version`
	log $script INFO "Grinder version: $resp"

	resp=`loop_until_match 10 5 'RUNNING' agents_status`
	log $script INFO "Agent status: $resp"
}

#------------------------------------------------------------------------------
#                               Main task
#------------------------------------------------------------------------------
# suspend_error_handler

# TODO: fix gridnertool to avoid exportation need
export JAVA_HOME

log $script INFO "Stop previous Grinder if any ..."
stop_grinder

log $script INFO "Start console..."
sh ${GRINDERTOOL_DIR}/bin/startConsole.sh -p ${GRINDERTOOL_CONSOLE_PORT} -j ${GRINDERTOOL_JETTY_PORT} -- -headless >/dev/null 2>&1 &

log $script INFO "Waiting a little..."
sleep 10

#
# Here we could imagine to launch *** ALL the agents *** and not only one ...
# requirement: Remote SSH command if keys deployed
#
log $script INFO "Start agent..."
sh ${GRINDERTOOL_DIR}/bin/startAgent.sh -p ${GRINDERTOOL_CONSOLE_PORT} 


log $script INFO "End of script."
echo ""
