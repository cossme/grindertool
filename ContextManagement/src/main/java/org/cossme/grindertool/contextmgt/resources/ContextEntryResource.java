package org.cossme.grindertool.contextmgt.resources;

//import java.util.concurrent.atomic.AtomicLong;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import javax.servlet.http.HttpServletResponse;
import javax.ws.rs.Consumes;
import javax.ws.rs.GET;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;
import javax.ws.rs.Produces;
import javax.ws.rs.core.Context;
import javax.ws.rs.core.MediaType;

import org.apache.http.HttpRequest;
import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.codahale.metrics.annotation.Timed;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.cossme.grindertool.contextmgt.core.ContextCreationResponse;
import org.cossme.grindertool.contextmgt.core.ContextData;
import org.cossme.grindertool.contextmgt.core.ContextEntry;
import org.cossme.grindertool.contextmgt.core.ContextEntryCache;
import org.cossme.grindertool.contextmgt.core.ContextStats;

@Path("/context")
@Produces(MediaType.APPLICATION_JSON)
public class ContextEntryResource {
	static final Logger LOG = LoggerFactory.getLogger(ContextEntryCache.class);

	private HttpClient grinderHttpClient;

	public ContextEntryResource(HttpClient httpClient) {
		this.grinderHttpClient = httpClient;
	}

	@Path("/ping")
	@GET
	@Timed
	public String ping() {
		return "alive";
	}

	@Path("/stats")
	@GET
	@Timed
	public List<ContextStats> printStats() {
		return ContextEntryCache.getInstance().getStats();
	}

	@Path("/dump")
	@GET
	@Timed
	public Map<String, Map<String, ContextEntry>> dumpCache() {
		return ContextEntryCache.getInstance().dump();
	}

	@Path("create")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse createContext(ContextEntry context) {
		// Mark single notification
		context.setMultipleNotification();
		ContextEntryCache.getInstance().addElement(context);
		LOG.info("**CREATE done** >> {}", context.toString());
		return new ContextCreationResponse("done");
	}


	@Path("createBatch")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse createBatchContext(ContextEntry[] contextList) {
		
		for (ContextEntry elem: contextList) {
			createContext(elem);
		}
		return new ContextCreationResponse("done");
	}

	
	@Path("delete")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse deleteContext(ContextEntry context) {
		ContextEntryCache.getInstance().remove(context.getContextKey(),
				context.getValue());
		LOG.info("**DELETE** >> {}", context.toString());
		return new ContextCreationResponse("done");
	}

	/*
	 * Route Callback Json information to the good grindertool worker (http
	 * client call) if we find the key,value in the ContextEntryCache singleton.
	 */
	@Path("update")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse updateContext(ContextData context) {

		LOG.info("**UPDATE start** >> {}", context.toString());
		// *** 1 *** First we look for the key/value in the ContextEntryCache
		ContextEntry cached = ContextEntryCache.getInstance().findInContext(
				context.getContextKey(), context.getValue());
		if (cached != null) {

			// *** 2 *** Serialize object to Json
			String JSON = null;
			ObjectMapper mapper = new ObjectMapper();
			try {
				JSON = mapper.writeValueAsString(context);
				LOG.debug("\t...Serialize ContextData to Json:" + JSON);
				// System.out.println(JSON);
			} catch (JsonProcessingException e) {
				LOG.error("Serialization exception for {}, \ntrace: {}", JSON,
						e.getStackTrace().toString());
				// e.printStackTrace();
			}

			String uri = String.format("http://%s:%s/callback/1",
					cached.getHost(), cached.getPort());
			LOG.debug("\t...target URI: {}", uri);

			// Post with json content
			HttpPost httpPost = new HttpPost(uri);
			httpPost.addHeader("Content-Type", "application/json");
			httpPost.setEntity(new StringEntity(JSON, "UTF-8"));
			try {
				HttpResponse response = this.grinderHttpClient
						.execute(httpPost);
				int res_code = response.getStatusLine().getStatusCode();
				LOG.debug("\t...After URI call: {}, Return code={} ", uri,
						res_code);

				// *** 4 *** remove entry from cache
				if (res_code == 200) {
					ContextEntryCache.getInstance().remove(
							context.getContextKey(), context.getValue());
				}

			} catch (IOException e) {
				LOG.error("Http call failed, \ntrace: {}", e);
			} finally {
				try {
					httpPost.releaseConnection();
				} catch (Exception e) {
					LOG.error("HttpPost releaseConnection failed, \ntrace: {}",
							e);
				}
			}
			// I don't think we have to release() the connection ... so i do
			// nothing for the moment

		}
		LOG.info("**UPDATE end**");
		return new ContextCreationResponse("done");
	}

	@Path("updateFromHeader")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse updateFromHeader(
			HashMap<String, String> context, @Context HttpRequest request,
			@Context final HttpServletResponse response) {

		LOG.info("**updateFromHeader start ** >> {}", context.toString());

		String contextKey = null;
		try {
			contextKey = request.getFirstHeader("X-Context-Key").getValue();
		} catch (Exception e) {
			LOG.error(
					"UpdateDirect failed getting header \"X-Context-Key\", \ntrace: {}",
					e);
			// set HTTP code to "404"
			response.setStatus(HttpServletResponse.SC_NOT_FOUND);
			try {
				response.flushBuffer();
			} catch (Exception ex2) {
			}
			return null;
		}

		String contextValue = context.get(contextKey);

		ContextData contextData = new ContextData();
		contextData.setContextKey(contextKey);
		contextData.setValue(contextValue);
		contextData.setData(context);

		ContextCreationResponse result = updateContext(contextData);

		LOG.info("**updateFromHeader end**");
		return result;
	}

	@Path("updateFromPath/{identifier: [a-zA-Z][a-zA-Z_/0-9]+}")
	@Consumes(MediaType.APPLICATION_JSON)
	@POST
	@Timed
	public ContextCreationResponse updateFromPath(
			HashMap<String, Object> context,
			@PathParam("identifier") String path,
			@Context final HttpServletResponse response) {

		LOG.info("**updateFromPath start [path={}] ** >> payload={}", path,
				context.toString());

		// contextKey in in the path and before the "/"
		String contextKey = path.split("/")[0];
		if (contextKey == null) {
			LOG.error(
					"Incorrect path \"{}\", we must have at least one \"/\" character in it",
					path);
			// set HTTP code to "404"
			response.setStatus(HttpServletResponse.SC_NOT_FOUND);
			try {
				response.flushBuffer();
			} catch (Exception e) {
			}
			return null;
		}

		// contextValue MUST BE in the JSON POST data
		LOG.info("updateFromPath - contextKey=\"{}\"", contextKey);
		String contextValue = context.get(contextKey).toString();
		if (contextValue == null) {
			LOG.error(
					"Incorrect context: {}, we must have the key \"{}\" inside",
					context, contextKey);
			// set HTTP code to "404"
			response.setStatus(HttpServletResponse.SC_NOT_FOUND);
			try {
				response.flushBuffer();
			} catch (Exception e) {
			}
			return null;
		}


		// Check if we have got all notifications
		if (!ContextEntryCache.getInstance().checkNotifications(contextKey,
				contextValue, context)) {
			response.setStatus(HttpServletResponse.SC_OK);
			try {
				response.flushBuffer();
			} catch (Exception e) {
			}
			return null;
		}

		HashMap<String,String> outputMap = ContextEntryCache.getInstance().findInContext(contextKey, contextValue).getOutputMap();
		
		// new property "X-path" in the output map
		outputMap.put("X-path", path);

		// The JSON callback structure
		ContextData contextData = new ContextData();
		contextData.setContextKey(contextKey);
		contextData.setValue(contextValue);
		contextData.setData(outputMap);

		ContextCreationResponse result = updateContext(contextData);

		LOG.info("**updateFromPath end**");
		return result;

	}

}