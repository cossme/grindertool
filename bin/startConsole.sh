#!/bin/bash

scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"

function display_help {
    echo -e "\nUsage:\n$0 [arguments]" 
	echo -e "\t-p|--port <port>  : grinder port"
	echo -e "\t-j|--jetty <port> : jetty Restfull API port"
	echo -e "\t-H|--headless     : switch to headless (NO GUI) mode"
	echo -e "\t-f|--property <property_file> : grinder property file"
	echo -e "\n"
    }

#-------------------------------------------------------------------------------------------------
# Default value
#-------------------------------------------------------------------------------------------------

GRINDERBASE=`dirname "${scriptPath}"`
cd "${GRINDERBASE}"

GRINDERPORT=6372
JETTYPORT=6373
PROPERTY_FILE=${GRINDERBASE}/console/dummy.properties
CLASSPATH=${GRINDERBASE}/grinder-3.11/lib/grinder.jar
SCRIPT=${GRINDERBASE}/console/grindertool.py
DISTRIBUTION_FILE="${GRINDERBASE}/console" 
HEADLESS=""

#-------------------------------------------------------------------------------------------------
# Script parameters processing
#-------------------------------------------------------------------------------------------------

while true
do
    case "$1" in
    -p | --port)
	  GRINDERPORT="$2"   # You may want to check validity of $2
	  shift 2
	  ;;
    -j | --jetty)
	  JETTYPORT="$2" # You may want to check validity of $2
	  shift 2
	  ;;
    -H | --headless)
	  HEADLESS="-headless" 
	  shift 1
	  ;;
    -f | --property)
	  PROPERTY_FILE="$2" # You may want to check validity of $2
	  shift 2

      if [ ! -f "${PROPERTY_FILE}" -a -f "${GRINDERBASE}/console/${PROPERTY_FILE}" ]; then
        PROPERTY_FILE="${GRINDERBASE}/console/${PROPERTY_FILE}"
      else
        echo "property file $PROPERTY_FILE doesn't exist. Aborting."
        exit 1
      fi
	  ;;
    -h | --help)
	  display_help  # Call your function
	  # no shifting needed here, we're done.
	  exit 0
	  ;;
    -v | --verbose)
          #  It's better to assign a string, than a number like "verbose=1"
	  #  because if you're debugging script with "bash -x" code like this:
	  #
	  #    if [ "$verbose" ] ...
	  #
	  #  You will see:
	  #
	  #    if [ "verbose" ] ...
	  #
          #  Instead of cryptic
	  #
	  #    if [ "1" ] ...
	  #
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

if [ -z "$JAVA_HOME" -o ! -d "$JAVA_HOME/bin" ]; then
    echo "Invalid JAVA_HOME"
    exit 1
fi

PARAMETERS=" -Dgrinder.console.propertiesFile=${PROPERTY_FILE} -Dgrinder.console.scriptDistributionDirectory=${DISTRIBUTION_FILE} -Dgrinder.script=${SCRIPT} -Dgrinder.console.consolePort=${GRINDERPORT} -Dgrinder.console.httpPort=${JETTYPORT} -cp ${CLASSPATH}"

CMD="$JAVA_HOME/bin/java -Xmx256m -XX:MaxPermSize=192m ${PARAMETERS} net.grinder.Console $HEADLESS $*"

echo "With JAVA_HOME : $JAVA_HOME"
echo "With CLASSPATH : $CLASSPATH"
echo "Running $CMD"

${CMD}
