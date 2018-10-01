#!/bin/bash
# this is a tiny helper script if you want to run 
# parts of the grindertool in standalone jython mode.
# i.e. grinder/console/corelibs$ ../../bin/runJython.sh GrinderStatsdReporter.py


# deduce current location from this script
WD=`pwd`
scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"
cd $scriptPath

GRINDERBASE="$scriptPath/.."
cd ${GRINDERBASE}
GRINDERBASE="`pwd`"

if [[ -n "${USE_GRINDERPORT}" ]] ; then
	GRINDERPORT=${USE_GRINDERPORT}
fi

cd ${GRINDERBASE}/grinder*/lib/
JYTHON_JAR=`pwd`
CP=${JYTHON_JAR}/`ls jython-*jar`

if [ ! -z "$CLASSPATH" ]
then
  CP=$CP:$CLASSPATH
fi

export JYTHONPATH="${GRINDERBASE}/extlib"

# go back where we started at...
cd $WD
$JAVA_HOME/bin/java -Dpython.home=${GRINDERBASE}/lib/ -classpath "$CP" org.python.util.jython "$@"
