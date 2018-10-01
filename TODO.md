
Make the grindertool build :
=============================

- libs in workspace/libs/core
      log4j.jar  
	  log4j.properties
	  snakeyaml-1.13.jar
	  ssh/
	      commons-logging-1.1.1.jar  
		  jsch_ssh.jar
		  
	  http/
	      httpclient-4.3.4.jar
          httpcore-4.3.2.jar
	  json/
	      commons-beanutils-1.8.3.jar    
		  commons-lang-2.6.jar       
		  ezmorph-1.0.6.jar       
		  jsonassert-1.4.0_patched.jar
          commons-collections-3.2.1.jar  
		  commons-logging-1.1.1.jar  
		  json-lib-2.4-jdk15.jar
	  

- context manager build
- integration of cossme/grinder snapshot
- zip grindertool.tgz
- push to snapshot on oss.sonatype.org


ssh library: jcraft
======================
<!-- https://mvnrepository.com/artifact/com.jcraft/jsch -->
<dependency>
    <groupId>com.jcraft</groupId>
    <artifactId>jsch</artifactId>
    <version>0.1.54</version>
</dependency>