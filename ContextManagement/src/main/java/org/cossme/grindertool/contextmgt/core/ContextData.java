package org.cossme.grindertool.contextmgt.core;

import java.util.HashMap;

import com.fasterxml.jackson.annotation.JsonProperty;


public class ContextData {


    private String contextKey;
    private String value;
    private HashMap<String,String> data;
    
    public ContextData() {
        // Jackson deserialization
    }

    public ContextData(String contextKey ) {
        this.setContextKey(contextKey);
    }


    @JsonProperty
	public String getContextKey() {
		return contextKey;
	}

    @JsonProperty
	public void setContextKey(String contextKey) {
		this.contextKey = contextKey;
	}

    @JsonProperty
	public String getValue() {
		return value;
	}

    @JsonProperty
	public void setValue(String value) {
		this.value = value;
	}

	
	@Override
	public String toString() {
		// TODO Auto-generated method stub
		return String.format("[contextKey=%s][value=%s]", this.contextKey, this.value);
	}

	public HashMap<String,String> getData() {
		return data;
	}

	public void setData(HashMap<String,String> data) {
		this.data = data;
	}

}