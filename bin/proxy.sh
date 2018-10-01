CLASSPATH=/product/integration/grindertool3.11/grinder-3.11/lib/grinder.jar
export CLASSPATH
 
java net.grinder.TCPProxy -localhost $1 -localport $2
