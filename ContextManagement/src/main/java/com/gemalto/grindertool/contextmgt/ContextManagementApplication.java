package org.cossme.grindertool.contextmgt;

import org.apache.http.client.HttpClient;

import io.dropwizard.Application;
import io.dropwizard.client.HttpClientBuilder;
import io.dropwizard.setup.Bootstrap;
import io.dropwizard.setup.Environment;

import org.cossme.grindertool.contextmgt.core.ContextEntryCleanerManager;
import org.cossme.grindertool.contextmgt.health.TemplateHealthCheck;
import org.cossme.grindertool.contextmgt.resources.ContextEntryResource;

public class ContextManagementApplication extends
		Application<ContextManagementConfiguration> {
	
	public static void main(String[] args) throws Exception {
		new ContextManagementApplication().run(args);
	}

	@Override
	public String getName() {
		return "ContextManagement";
	}

	@Override
	public void initialize(Bootstrap<ContextManagementConfiguration> bootstrap) {
		// nothing to do yet
	}

	@Override
	public void run(ContextManagementConfiguration configuration,
			Environment environment) {

		final HttpClient httpClient = new HttpClientBuilder(environment).using(
				configuration.getHttpClientConfiguration()).build(
				configuration.getGrindertoolClientName());

		
		final TemplateHealthCheck healthCheck = new TemplateHealthCheck(
				configuration.getTemplate());
		
		environment.healthChecks().register("template", healthCheck);
		
		environment.jersey().register(new ContextEntryResource(httpClient));
		
		// Register here a hook to start/stop the cleaning thread   
        environment.lifecycle().manage( new ContextEntryCleanerManager( environment.metrics()));
		
	}

}