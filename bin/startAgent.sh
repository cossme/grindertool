#!/bin/bash

scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"

function display_help {
    echo -e "\nUsage:\n$0 [arguments]" 
	echo -e "\t-p|--port <port>      : grinder port"
	echo -e "\t-H|--host <hostname>  : grinder host"
	echo -e "\t-i|--id   <hostID>    : grinder hostID - unique agent identifier"
	echo -e "\t-d|--dir  <directory> : grinder agent base directory"
	echo -e "\n"
    }

#-------------------------------------------------------------------------------------------------
# Default value
#-------------------------------------------------------------------------------------------------

GRINDERBASE=`dirname "${scriptPath}"`
cd "${GRINDERBASE}"

HOSTID=`hostname`
GRINDERPORT=6372
GRINDERHOST=localhost
JYTHONPATH="${GRINDERBASE}/console/pythonlibs"
GRINDERPATH=${GRINDERBASE}/grinder-3.11

COMMON_CLASSPATH="${GRINDERBASE}/console:${GRINDERBASE}/console/libs:$GRINDERPATH/lib/grinder-dcr-agent-3.11.jar:$GRINDERPATH/lib/grinder-core-3.11.jar:$GRINDERPATH/lib/asm-3.2.jar:$GRINDERPATH/lib/extra166y-1.7.0.jar:$GRINDERPATH/lib/slf4j-api-1.6.4.jar:$GRINDERPATH/lib/logback-core-1.0.0.jar:$GRINDERPATH/lib/logback-classic-1.0.0.jar:$GRINDERPATH/lib/jython-standalone-2.5.3.jar:$GRINDERPATH/lib/picocontainer-2.13.6.jar:$GRINDERPATH/lib/grinder-httpclient-3.11.jar:$GRINDERPATH/lib/grinder-http-3.11.jar"

for jar in `ls ${GRINDERBASE}/console/libs/extlibs/*.jar`
do
  COMMON_CLASSPATH=$COMMON_CLASSPATH:$jar
done

JSON_CLASSPATH="${COMMON_CLASSPATH}:$GRINDERPATH/lib/json/json-lib-2.4-jdk15.jar:$GRINDERPATH/lib/json/commons-beanutils-1.8.3.jar:$GRINDERPATH/lib/json/commons-collections-3.2.1.jar:$GRINDERPATH/lib/json/commons-lang-2.6.jar:$GRINDERPATH/lib/json/commons-logging-1.1.1.jar:$GRINDERPATH/lib/json/ezmorph-1.0.6.jar"

WITH_JSON=no

# for those who need to be exported...
export JYTHONPATH

#-------------------------------------------------------------------------------------------------
# Script parameters processing
#-------------------------------------------------------------------------------------------------

while true
do
    case "$1" in
    -H | --host)
	  GRINDERHOST="$2"
	  shift 2
	  ;;
    -p | --port)
	  GRINDERPORT="$2"
	  shift 2
	  ;;
    -i | --id)
	  HOSTID="$2"
	  shift 2
	  ;;
    -d | --dir)
	  DIRECTORY="$2"
	  shift 2
	  ;;
    -J | --json)
      WITH_JSON=yes
      shift 1
      ;;
    -h | --help)
	  display_help  # Call your function
	  # no shifting needed here, we're done.
	  exit 0
	  ;;
    -v | --verbose)
	  verbose="verbose"
	  shift
	  ;;
    --) # End of all options
	  shift
	  break
      ;;
    -*)
	  echo "Error: Unknown option: $1" >&2
	  display_help
	  exit 1
	  ;;
    *)  # No more options
	  echo "No more options"
	  break
	  ;;
    esac
done

# TODO: understand and maybe change log behavior...
if [ ! -n ${DIRECTORY} ]; then
        DIRECTORY=/var/tmp/${LOGNAME}
fi
mkdir -p ${DIRECTORY}
cd ${DIRECTORY}

if [ "${WITH_JSON}" = "yes" ]; then
    CLASSPATH="${JSON_CLASSPATH}"
else
    CLASSPATH="${COMMON_CLASSPATH}"
fi

if [ -z "$JAVA_HOME" -o ! -d "$JAVA_HOME/bin" ]; then
    echo "Invalid JAVA_HOME"
    exit 1
fi

CMD="$JAVA_HOME/bin/java -Dgrinder.logDirectory=${DIRECTORY} -Dgrinder.hostID=$HOSTID -Dgrinder.consoleHost=$GRINDERHOST -Dgrinder.consolePort=$GRINDERPORT -cp $CLASSPATH net.grinder.Grinder $GRINDERPROPERTIES"

echo "With JAVA_HOME : $JAVA_HOME"
echo "With CLASSPATH : $CLASSPATH"
echo "Running $CMD"

${CMD}
