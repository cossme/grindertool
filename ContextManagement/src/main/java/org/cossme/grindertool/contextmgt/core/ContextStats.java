package org.cossme.grindertool.contextmgt.core;

import com.fasterxml.jackson.annotation.JsonProperty;


public class ContextStats {


    private String contextKey;
    private int count;
    
    public ContextStats() {
        // Jackson deserialization
    }

    public ContextStats(String contextKey, int count ) {
        this.setContextKey(contextKey);
        this.setCount(count);
    }

    public ContextStats(String contextKey ) {
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
	public int getCount() {
		return count;
	}
    @JsonProperty
	public void setCount(int count) {
		this.count = count;
	}


}