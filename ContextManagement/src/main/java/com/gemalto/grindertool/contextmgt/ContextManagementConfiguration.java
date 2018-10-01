package org.cossme.grindertool.contextmgt;

import javax.validation.Valid;
import javax.validation.constraints.NotNull;

import io.dropwizard.Configuration;

import io.dropwizard.client.HttpClientConfiguration;

import com.fasterxml.jackson.annotation.JsonProperty;

import org.hibernate.validator.constraints.NotEmpty;

public class ContextManagementConfiguration extends Configuration {
	@NotEmpty
	private String template;

	@NotEmpty
	private String defaultName = "Stranger";
	
	@NotEmpty
	private String grindertoolClientName = "grindertool";

	@JsonProperty
	public String getTemplate() {
		return template;
	}

	@JsonProperty
	public void setTemplate(String template) {
		this.template = template;
	}

	@JsonProperty
	public String getGrindertoolClientName() {
		return grindertoolClientName;
	}
	
	
	@JsonProperty
	public String getDefaultName() {
		return defaultName;
	}

	@JsonProperty
	public void setDefaultName(String name) {
		this.defaultName = name;
	}

	@Valid
	@NotNull
	@JsonProperty
	private HttpClientConfiguration httpClient = new HttpClientConfiguration();

	public HttpClientConfiguration getHttpClientConfiguration() {
		return httpClient;
	}
}