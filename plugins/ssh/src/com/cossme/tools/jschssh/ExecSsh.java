/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package com.cossme.tools.jschssh;

import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;

import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.Validate;
import org.apache.commons.lang3.math.NumberUtils;

import com.jcraft.jsch.Channel;
import com.jcraft.jsch.ChannelExec;
import com.jcraft.jsch.JSch;
import com.jcraft.jsch.Session;

/**
 *
 * @author afabri
 */
public class ExecSsh {

	private static final String SSH_STRING_PATTERN 	= "[-0-9a-zA-Z.+_]+@[-0-9a-zA-Z.+_]+";
	private static final String SSH_COMMENT_PATTERN = "^\\s*?#.*$";
	
	private static final int 	SSH_DEFAULT_PORT 	= 22;
	private static final int 	ERROR_CODE 			= 500;
	
	private static String newLine = System.lineSeparator();
	
	
	/**
	 * 
	 * @param host: ssh connection String in the form <user>@<host>
	 * @param portSsh
	 * @param commands
	 * @param privateKey
	 * @param env
	 * @param result
	 * @return int commandStatus
	 */
	public int runCommand(String host, String portSsh, List commands,
			String privateKey, List<String> env, StringBuffer result) {

		int retVal = 0;
		int port = 0;
		String commandList = "source ~/.bashrc; source ~/.profile; ";

		try {

			Validate.matchesPattern(host, SSH_STRING_PATTERN);
			commands = Validate.notEmpty(commands);
			privateKey = Validate.notEmpty(privateKey);
			port = ((portSsh != null) && (NumberUtils.isDigits(portSsh))) ? Integer
					.parseInt(portSsh) : SSH_DEFAULT_PORT;

		} catch (Exception e) {
			System.out.println("SSH Connection's parameters Exception: " + e + newLine);
			System.out.println("One of the following, mandatory parameter, is missing or malformed: " + newLine);
			System.out.println("	1)   Ssh connection string in the form <user>@<host> " + newLine);
			System.out.println("	2)   Ssh Port, if not provided default value is 22 " + newLine);
			System.out.println("	3)   Command(s) to be run " + newLine);
			System.out.println("	4)   Ssh Authentication key " + newLine);			
			return ERROR_CODE;
		}

		commandList += StringUtils.join(commands, ";");
		
		System.out.println("Commands to be run are: " + commandList + "  " + newLine);

		try {

			env = Validate.notEmpty(env);
			commandList = envBuilder(commandList, env);

		} catch (Exception e1) {

			System.out.println("WARNING: Properties were empty; You chose to not provide any ENV through property file");

		}
		
		System.out.println("Full cmd line sent is: " + commandList + "  ");
		
		try {

			JSch jsch = new JSch();

			String user = host.substring(0, host.indexOf('@'));
			host = host.substring(host.indexOf('@') + 1);

			jsch.addIdentity(privateKey);
			System.out.println("identity added ");

			Session session = jsch.getSession(user, host, port);
			System.out.println("session created.");

			java.util.Properties config = new java.util.Properties();
			config.put("StrictHostKeyChecking", "no");
			config.put("PreferredAuthentications",
					"publickey,keyboard-interactive,password");
			session.setConfig(config);
			session.connect();

			Channel channel = session.openChannel("exec");
			((ChannelExec) channel).setCommand(commandList);

			channel.setInputStream(null);

			((ChannelExec) channel).setErrStream(System.err);

			InputStream in = channel.getInputStream();

			channel.connect();

			byte[] tmp = new byte[1024];
			while (true) {
				while (in.available() > 0) {
					int i = in.read(tmp, 0, 1024);
					if (i < 0) {
						break;
					}

					result.append(new String(tmp, 0, i));
				
				}
				if (channel.isClosed()) {
					if (in.available() > 0) {
						continue;
					}

					retVal = channel.getExitStatus();
				
					break;
				}
				try {
					Thread.sleep(1000);
				} catch (Exception ee) {
				}
			}
			channel.disconnect();
			session.disconnect();

		} catch (Exception e) {
			System.out.println(e);
		}

		return retVal;

	}
	
	/**
	 * 
	 * @param commandList
	 * @param prop
	 * @return
	 */
	private String envBuilder(String commandList, List<String> lines) {
		
		LinkedHashMap<String, String> map = new LinkedHashMap<String, String>();
		
		for (String line: lines){			
			final String split[] = line.split("=");
			
			if ((split.length != 2) || (StringUtils.isAnyBlank(split[0], split[1])))
				continue;			
			
			try {
				Validate.matchesPattern(line, SSH_COMMENT_PATTERN);
			} catch (Exception e) {
				if (!(map.containsKey(split[0])))
						map.put(split[0], split[1]);
				else {						
					String existingValue = map.get(split[0]);
					map.put(split[0], existingValue + ":" + split[1]);
				}
			}			
		}
		
		StringBuilder env = new StringBuilder();
		Set<String> keys = map.keySet();
		String result;

		for(String key: keys){ 
			env.append("export ");
			env.append(key);
			env.append("=");
			env.append(map.get(key));
			if(key.contains("PATH")){
				env.append(":");
				env.append("$" + key + "; ");
			}else{
				env.append("; ");
			}
		}

		result = env.toString() + commandList;
		return result;
	}

}
