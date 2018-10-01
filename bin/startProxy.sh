#!/usr/bin/sh

# deduce current location from this script
scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"
cd $scriptPath

GRINDERBASE="$scriptPath/.."

. ${GRINDERBASE}/setGrinderEnv.sh

echo "using CLASSPATH : $CLASSPATH"
if [[ -n "${GRINDERPORT}" ]] ; then
	$JAVA_HOME/bin/java -Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=$JMXPORT -Dcom.sun.management.jmxremote.ssl=false -Dcom.sun.management.jmxremote.authenticate=false -Dgrinder.console.consolePort=$GRINDERPORT -cp $CLASSPATH net.grinder.TCPProxy -localhost 10.10.164.47 -console -http> $1
else
	$JAVA_HOME/bin/java -cp $CLASSPATH -Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=$JMXPORT -Dcom.sun.management.jmxremote.ssl=false -Dcom.sun.management.jmxremote.authenticate=false net.grinder.TCPProxy -localhost 10.10.164.47 -console -http> $1
fi
