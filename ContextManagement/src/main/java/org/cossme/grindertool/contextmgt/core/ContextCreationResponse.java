package org.cossme.grindertool.contextmgt.core;

import com.fasterxml.jackson.annotation.JsonProperty;
import org.hibernate.validator.constraints.Length;

public class ContextCreationResponse {

    @Length(max = 3)
    private String content;

    public ContextCreationResponse() {
        // Jackson deserialization
    }

    public ContextCreationResponse(String content) {
        this.content = content;
    }


    @JsonProperty
    public String getContent() {
        return content;
    }
}