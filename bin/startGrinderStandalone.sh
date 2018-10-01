scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"

GRINDERBASE=`dirname "${scriptPath}"`
cd "${GRINDERBASE}"


# param 1 (req): ***** property file to execute ****
if [ -z "$1" ]; then
    echo "Specify the property file you want to launch"
    exit 1
fi

# Check there is a property file
GRINDERPROPERTIES=$1	

# param 2 (opt): ***** Log Location ****
LOG="../log"
if [ ! -z "$2" ]; then
   LOG=$2
   if [ ! -d ${LOG} ]; then
      mkdir -p ${LOG}
   fi
fi


#
# To be in the good directory for standalone mode
# 
cd ${GRINDERBASE}/console

#
# The property file should exists there
#
if ! test -f $GRINDERPROPERTIES; then 
    echo "The property file \"$GRINDERPROPERTIES\" do not exists in console subdirectory"
    exit 1
fi

#
# JAVA HOME should be checked
#
if [ -z "$JAVA_HOME" ]; then
   JAVA_HOME=/opt/java1.7
else
   JAVA_HOME=$JAVA_HOME
fi
if ! test -f "$JAVA_HOME/bin/java"; then
   echo "JAVA_HOME=$JAVA_HOME is not correct, could you check ?"
   exit 2
fi
PATH=$JAVA_HOME/bin:$PATH

#
# JYTHON PATH is necessary only for pure PYTHON libraries
# Libraries must be available from the agent
# 
export JYTHONPATH=pythonlibs:pythonlibs/statsd
GRINDERPATH=../grinder-3.11

CLASSPATH="${GRINDERBASE}/console/libs:${GRINDERBASE}/console:$CLASSPATH:$GRINDERPATH/lib/grinder-dcr-agent-3.11.jar:$GRINDERPATH/lib/grinder-core-3.11.jar:$GRINDERPATH/lib/asm-3.2.jar:$GRINDERPATH/lib/extra166y-1.7.0.jar:$GRINDERPATH/lib/slf4j-api-1.6.4.jar:$GRINDERPATH/lib/logback-core-1.0.0.jar:$GRINDERPATH/lib/logback-classic-1.0.0.jar:$GRINDERPATH/lib/jython-standalone-2.5.3.jar:$GRINDERPATH/lib/picocontainer-2.13.6.jar:$GRINDERPATH/lib/grinder-httpclient-3.11.jar:$GRINDERPATH/lib/grinder-http-3.11.jar"

#
# Start the agent in daemon mode (try to reconnect to the console every 10 seconds)
# 
java -Dgrinder.useConsole=False -Dgrinder.logDirectory="${LOG}" -Dgrinder.logLevel=error -Dgrinder.console.propertiesFile=$GRINDERPROPERTIES -classpath $CLASSPATH net.grinder.Grinder  $GRINDERPROPERTIES

