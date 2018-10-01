To start the context router:
- update the context.yml configuration file 
- copy the fat jar in target directory 

Launch the command:
java -Xms256m -Xmx512m -jar target/contextmgt-0.3.-SNAPSHOT.jar server context.yml


PRE-REQUISITE: you need java 1.7 in your PATH

REMARKS:
- -Xms and -Xmx options are not necessary for validation usage