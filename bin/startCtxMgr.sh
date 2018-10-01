#
PATH=${JAVA_HOME}\bin:${PATH}

#
#  Go to the relative target directory
#
cd ../ContextManagement

#
# Start the context Manager process
# 
java -Xms256m -Xmx512m -jar contextmgt.jar server context.yml
