#!/bin/bash
scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"
cd $scriptPath

if test -z "$JAVA_HOME"; then
  export JAVA_HOME=/opt/java1.7
fi

GRINDERBASE=${scriptPath}
GRINDERPATH=${GRINDERBASE}/grinder-3.11
GRINDERLIB=${GRINDERPATH}/lib
TESTNAME=${scriptName}
property_file=`basename ${TESTNAME}`
echo "GRINDERBASE=$GRINDERBASE" 
echo "GRINDERPATH=$GRINDERPATH"
echo "GRINDERLIB=$GRINDERLIB"
echo "TESTNAME=$TESTNAME"
if [ -z "$1" ]
  then
    echo "please provide the path to the property file"
    exit
fi
property_file=$(basename $1)
echo ${property_file}


#------------------------------
CLASSPATH=${scriptPath}
CLASSPATH="${GRINDERLIB}:${GRINDERLIB}/grinder.jar:${GRINDERLIB}/grinder-core-3.11.jar:${GRINDERLIB}/grinder-http-3.11.jar:${GRINDERLIB}/grinder-swing-console-3.11.jar:${GRINDERLIB}/jython-standalone-2.5.3.jar:${CLASSPATH}"
CLASSPATH_CONSOLE=${CLASSPATH}
# =============== > core libraries <=================
for lib in `ls ${GRINDERBASE}/console/libs/core/*.jar ${GRINDERBASE}/console/libs/core/json/*.jar ${GRINDERBASE}/console/libs/core/http/*.jar 2>/dev/null` ; do
  CLASSPATH="$lib:${CLASSPATH}"
done
# =============== > SmscToolkit libraries <=================
for lib in `ls ${GRINDERBASE}/smscToolkit/lib/*.jar ${GRINDERBASE}/smscToolkit/lib/ext/*.jar 2>/dev/null` ; do
  CLASSPATH="$lib:${CLASSPATH}"
done


function findNewAvailablePortNumber 
{
  _portNumber=$1   # starting port is passed in argument
  _is_used=0       #0 mean not used, greater then zero mean used
  
  # loop until a new port in found
  while true; do
    # Check if port is used or not
    _is_used=$( netstat -an | grep ${_portNumber} | wc -l)
    if [ ${_is_used} -eq 0 ]; then
        break
    fi
    _portNumber=$((100+${_portNumber}))

    if [ ${_portNumber} -gt 20000 ]; then
        # we exceed the rang of 20000, so use an arbirary starting port number and loop again
        _portNumber=`tr -cd 0-9 </dev/urandom | head -c 4`
        _portNumber=$((${_portNumber}+1024))
    fi
  done

  echo ${_portNumber}
}


# --- Generate a random port number
USE_GRINDERPORT=$( findNewAvailablePortNumber $((2000+${EUID})))
JETTY_PORT=$( findNewAvailablePortNumber  $((${USE_GRINDERPORT}+100)))

echo "Loading java libraries..."
for library in `find ${scriptPath}/project/ -type f -name "*.jar" 2>/dev/null`; do
  CLASSPATH=${CLASSPATH}:${library}
done


# Load all python modules
#echo "Loading python module..."
#for library in `find ../project -type d | egrep -v "implementations|macros|functions" | egrep "^../project/.*/console/.*" | egrep -v "../project/.*/console/.*/.*"`; do
#  ln -s ${library} ${scriptPath}/console/`basename ${library}` 2>/dev/null
#done
# link all the python modules available on pythonlibs into console
# link all the python modules available on pythonlibs into console
JYTHONPATH="${GRINDERBASE}/console"
for lib in `find ${GRINDERBASE}/pythonlibs -maxdepth 1 -type d` ; do
linkname=${GRINDERBASE}/console/`basename ${lib}`
    if  [ ! -h ${linkname} ]; then
        ln -s ${lib} ${linkname}
    fi 
JYTHONPATH="${linkname}:${JYTHONPATH}"
done
export JYTHONPATH

GRINDERPROPERTIES=${property_file}

### ok export stuff :
export JAVA_HOME CLASSPATH CLASSPATH_CONSOLE PATH GRINDERPROPERTIES USE_GRINDERPORT JETTY_PORT

#Report back to shell whats usefull
echo "Your Grinderport is ${USE_GRINDERPORT}, Jetty-Port ${JETTY_PORT}"
echo export GRINDERPROPERTIES=$GRINDERPROPERTIES
echo export USE_GRINDERPORT=$USE_GRINDERPORT
echo export JETTY_PORT=$JETTY_PORT
echo export JAVA_HOME=$JAVA_HOME
echo export CLASSPATH=$CLASSPATH
echo export CLASSPATH_CONSOLE=$CLASSPATH_CONSOLE
echo export JYTHONPATH=$JYTHONPATH

#
# --- Grindetool scenario description at the startup ...
#
scenario=`grep -i ^filein console/${property_file}|cut -d= -f2` 1>&2 1>/dev/null
inputfile=`grep -i ^dataFilePath console/${property_file}|cut -f2 -d=`
echo "============"
echo "Using [property=console/${property_file}] [scenario=${inputfile}/${scenario}]..."
echo "altering ~/.grinder_console accordingly"
echo "============"

#
# To set the property file directly if curl is not available on the host 
#
if test ! -e ~/.grinder_console; then
        echo "generating initial ~/.grinder_console file"
        echo "grinder.console.propertiesFile=blarg
grinder.console.scriptDistributionDirectory=blub
grinder.console.distributeAutomaticallyAsk=false
" > ~/.grinder_console
fi
echo sed -i -e "s,\(^grinder.console.propertiesFile\)=.*,\1=${property_file},g" ~/.grinder_console
echo sed -i -e "s,\(^grinder.console.scriptDistributionDirectory\)=.*,\1=${scriptPath}/console,g" ~/.grinder_console
sed -i -e "s,\(^grinder.console.propertiesFile\)=.*,\1=${property_file},g" ~/.grinder_console
sed -i -e "s,\(^grinder.console.scriptDistributionDirectory\)=.*,\1=${scriptPath}/console,g" ~/.grinder_console

if test -n "`netstat -plnt 2>/dev/null |grep :${USE_GRINDERPORT}`"; then
    echo "Grinder already running on port ${USE_GRINDERPORT}; Exit!"
    exit 1
fi

./bin/startConsole.sh&

# wait for the console to open the listener:
while test -z "`netstat -plnt 2>/dev/null |grep :${USE_GRINDERPORT}`"; do
    printf "."
    sleep 1
done

# Set the current property file using rest full api using curl
if hash curl 2>/dev/null; then
  while test -z "`netstat -plnt 2>/dev/null |grep :${JETTY_PORT}`"; do
      printf "."
      sleep 1
  done
fi
if ! hash curl 2>/dev/null; then
    echo "curl -H \"Content-Type: application/json\" -X PUT http://localhost:${JETTY_PORT}/properties -d '{\"distributionDirectory\":\"${scriptPath}/../console\", \"propertiesFile\":\"${property_file}\"}'"
    curl -H "Content-Type: application/json" -X PUT http://localhost:${JETTY_PORT}/properties -d "{\"distributionDirectory\":\"${scriptPath}/../console\", \"propertiesFile\":\"${property_file}\"}"
fi

./bin/startAgent.sh&
