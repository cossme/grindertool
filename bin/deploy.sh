#!/bin/bash
#set -x
PWD=`pwd`
# deduce current location from this script
scriptPath=`dirname $0`
scriptPath=`cd $scriptPath && /bin/pwd`
scriptName="$0"
cd $scriptPath

verbose=""

# funtion to display commands
echodo() {  
   if [ "x"${verbose} != "x" ]; then
     echo "\$ $@"  
   fi
   "$@"  
}

function display_help {
    echo -e "\nUsage:\n$0 [arguments]"
        echo -e "\t-d|--dir <directory>      : logs directory"
        echo -e "\t-s|--scenario <directory> : scenario location directory"
        echo -e "\t-p|--project <name>       : a project name existing under project directory"
        echo -e "\n"
    }

#-------------------------------------------------------------------------------------------------
# Script parameters processing
#-------------------------------------------------------------------------------------------------
while true
do
    case "$1" in
    -d | --dir)
          DIRECTORY="$2"
          shift 2
          ;;
    -s | --scenario)
          SCENARIO_DIR="$2"
          shift 2
          ;;
    -p | --project)
          PROJECT="$2"
          shift 2
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
          #echo "No more options"
          break
          ;;
    esac
done


GRINDERBASE="$scriptPath/.."
cd ${GRINDERBASE}
GRINDERBASE="`pwd`"


# 1) Check project & properties
#-------------------------------
if [ "x"${PROJECT} == "x" ]; then
   echo "Missing required parameter <-p|--project> !"
   display_help  
   exit 1
fi
if [ "x"${SCENARIO_DIR} == "x" ]; then
   echo "Missing required parameter <-s|--scenario> !"
   display_help  
   exit 1
fi

PROJECTDIR=${GRINDERBASE}/project/${PROJECT}
CONSOLEDIR=${GRINDERBASE}/console

if [ -d  ${PROJECTDIR} ]; then
   cp ${PROJECTDIR}/console/*.properties ${CONSOLEDIR}
else
   echo "project location: ${PROJECTDIR} not found !"
   exit 1
fi

# 2) link console/data to project project/console/data 
#-------------------------------------------------------
if [ ! -d ${SCENARIO_DIR} ]; then
  echodo mkdir -p ${SCENARIO_DIR}
  echo "Scenario will be located in: ${SCENARIO_DIR}"
fi
echodo rm -rf ${CONSOLEDIR}/data
echodo ln -s ${SCENARIO_DIR}/data ${CONSOLEDIR}/data
echodo cp -r ${PROJECTDIR}/console/data ${SCENARIO_DIR} 


# 3) link libs/extlibs to project/lib
#-------------------------------------
if [ -d ${PROJECTDIR}/lib ]; then
  for k in `ls ${PROJECTDIR}/lib`; do
      echodo rm -f ${CONSOLEDIR}/libs/extlibs/${k}
      echodo ln -s ${PROJECTDIR}/lib/${k} ${CONSOLEDIR}/libs/extlibs/${k}
  done
fi

# 4) link implementations and macros
#------------------------------------  
for k in macros implementations;
do
    LOC=${PROJECTDIR}/console/${k}
    if [ -d ${LOC} ]; then
        for x in `ls ${LOC}`; do
            VAR=`echo ${x}|grep ".py$"|wc -l`
            if [ ${VAR} -gt 0 ]; then
              echodo rm -f ${CONSOLEDIR}/${k}/${x}
              echodo ln -s ${LOC}/${x} ${CONSOLEDIR}/${k}/${x}
            fi
        done
    fi;
done
