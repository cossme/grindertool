SSH USAGE:

input parameters are:

1)  host.
    MANDATORY. 
    ssh connection string in the form: '<user@host>';  
    for example: 
        host: 'gemapp@vgerndvud1497'
    
2)  port.
    NOT MANDATORY, if not present, default is 22. 
    ssh connection port in the form: '<port_number>';  
    for example:
        port: '22'
        
3)  List commands.
    MANDATORY. 
    command(s) to run on server in the form; 
    for example:
            commands:          
                - cmd: 'ls -lrt'
                - cmd: 'printenv'
                
4)  identityPath.
    MANDATORY.
    path to ssh auth private key in the form: 'C:\\<PATH_TO_PRIVATE_KEY>\\id_rsa'; 
    for example:
        identityPath: 'C:\\Users\\<user>\\Desktop\\id_rsa_generic'    
    
5)  propertyFile.
    NOT MANDATORY. 
    path to a property file containing variables you want to propagate to the remote shell session, in the form: 'C:\\<PATH_TO_PROPERTY_FILE>'; 
    example of content:
            PID2KILL=`ps -fu tsmapp | grep managed1 | grep -v grep | awk '{ print $2 }'`
            WL_HOME=<YOUR_PATH>

            
Example of a YAML Scenario:

- scenario: 
    name: ssh command executor
    context:
         host: 'gemapp@<host>' 
         port: '22'     
         identityPath: 'C:\\id_rsa_generic'
         propertyFile: 'D:\\myProps.properties'         
    steps:
       - name: printhost
         protocol: procexec
         input:
            commands: 
                - cmd: 'hostname'             
         
       - name: somecommands
         protocol: procexec
         input:
            commands:          
                - cmd: 'ls -lrt'
                - cmd: 'printenv'
                
       - name: stopwlnode
         protocol: procexec
         input:
            commands:
                - cmd: 'echo ${PID2KILL}'
                - cmd: 'kill -9 echo ${PID2KILL}'

                
       - name: dummy step
         protocol: dummy