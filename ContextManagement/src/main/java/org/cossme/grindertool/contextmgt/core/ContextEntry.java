package org.cossme.grindertool.contextmgt.core;

import java.util.HashMap;


import com.fasterxml.jackson.annotation.JsonProperty;


public class ContextEntry {


    private String contextKey;
    private String value;
    private String host;
    private int port;
    private long expirationtime;
    // For multiple notification
    private HashMap<String,String> outputMap = new HashMap<String,String>();
    private int count;
    private boolean multipleNotification=false;

	public ContextEntry() {
        // Jackson deserialization
    }


	public boolean isMultipleNotification() {
		return multipleNotification;
	}


	public void setMultipleNotification() {
		if (count>1) {
			this.multipleNotification = true;
		}
	}


	public ContextEntry(String contextKey ) {
        this.setContextKey(contextKey);
    }


    @JsonProperty
	public String getContextKey() {
		return contextKey;
	}

	public void setContextKey(String contextKey) {
		this.contextKey = contextKey;
	}

    @JsonProperty
	public String getValue() {
		return value;
	}

	public void setValue(String value) {
		this.value = value;
	}

    @JsonProperty
	public String getHost() {
		return host;
	}

	public void setHost(String host) {
		this.host = host;
	}

    @JsonProperty
	public int getPort() {
		return port;
	}

	public void setPort(int port) {
		this.port = port;
	}

    @JsonProperty
	public long getExpirationtime() {
		return expirationtime;
	}

	public void setExpirationtime(long expirationtime) {
		this.expirationtime = expirationtime;
	}
	
    @JsonProperty
	public int getCount() {
		return count;
	}

	public void setCount(int count) {
		this.count = count;
	}
	public void decrement() {
		this.count--;
	}

    public void addMap(HashMap<String, String> myMap) {
    	outputMap.putAll(myMap);
		
	}
    public HashMap<String, String> getOutputMap() {
		return outputMap;
	}

	
	@Override
	public String toString() {
		// TODO Auto-generated method stub
		return String.format("[contextKey=%s][value=%s]", this.contextKey, this.value);
	}
}