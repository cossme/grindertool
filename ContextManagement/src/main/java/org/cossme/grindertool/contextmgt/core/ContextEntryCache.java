package org.cossme.grindertool.contextmgt.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ContextEntryCache {
	// Defines the logger
	static final Logger LOG = LoggerFactory.getLogger(ContextEntryCache.class);

	// Initialize the singleton
	private static final ContextEntryCache entryCacheInstance = new ContextEntryCache();

	// Mutex used to control access to the top level Map (ie context key map)
	private final Object mutex = new Object();

	// The cache that contains each context entry
	private final Map<String, Map<String, ContextEntry>> entryCache;

	// Return the singleton
	public static final ContextEntryCache getInstance() {
		return entryCacheInstance;
	}

	// Initialize the cache
	private ContextEntryCache() {
		entryCache = new HashMap<String, Map<String, ContextEntry>>();
	}

	/*
	 * Add a context entry
	 */
	public void addElement(ContextEntry c) {
		Map<String, ContextEntry> contextKeyMap = null;

		synchronized (mutex) {
			// Try to get the context key map
			contextKeyMap = entryCache.get(c.getContextKey());
			// if context key is not found then add a new one
			if (contextKeyMap == null) {
				contextKeyMap = Collections
						.synchronizedMap(new TreeMap<String, ContextEntry>());
				entryCache.put(c.getContextKey(), contextKeyMap);
			}
		}
		// finally update the context key map with the new value
		contextKeyMap.put(c.getValue(), c);
	}

	/*
	 * Find key, value in the cache
	 */
	public ContextEntry findInContext(String keyName, String keyValue) {
		ContextEntry found = null;
		synchronized (mutex) {
			Map<String, ContextEntry> key = entryCache.get(keyName);
			if (key == null) {
				LOG.error("Contextkey {} not found", keyName);
				return null;
			}
			found = entryCache.get(keyName).get(keyValue);
			if (found == null) {
				LOG.error("Identifier: (Contextkey {}, value {} ) not found", keyName, keyValue);
				return null;
			}
		}
		return found;
	}

	
	//
	// transcoding from <String,Object> to <String,String>
	// input object are flattened
	//
	private HashMap<String, String> transcode(HashMap<String, Object> context, int index, boolean multipleNotif) {
		HashMap<String, String> outputMap = new HashMap<String, String>();
		for (Map.Entry<String, Object> item : context.entrySet()) {
			
			LOG.debug(String.format("key=%s, value.class=%s", item.getKey(),
					item.getValue() != null?item.getValue().getClass():"null"));
			
			if (item.getValue() != null && item.getValue() instanceof Map) {
				@SuppressWarnings("unchecked")
				Map<String, Object> map = (Map<String, Object>) item.getValue();
				for (Map.Entry<String, Object> item2 : map.entrySet()) {
					outputMap.put(item.getKey() + ((multipleNotif)?index:"") + "." + item2.getKey(), 
							item2.getValue()!=null?item2.getValue().toString():"null");
				}
			} else {
				outputMap.put(item.getKey()+((multipleNotif)?index:""), item.getValue()!= null?item.getValue().toString():"null");
			}
		}
		return outputMap;
	}


	public boolean checkNotifications(String keyName, String keyValue, HashMap<String, Object> context) {
		synchronized (mutex) {
			Map<String, ContextEntry> key = entryCache.get(keyName);
			if (key == null) {
				LOG.error("Contextkey {} not found", keyName);
				return false;
			}
			ContextEntry entry=key.get(keyValue);
			if (entry == null) {
				LOG.error("Identifier: (Contextkey {}, value {} ) not found", keyName, keyValue);
				return false;
			}
			entry.addMap( transcode( context, entry.getCount(),entry.isMultipleNotification() ));
			if (entry.getCount()>1) {
				LOG.info("Notification {} received, waiting after others", entry.getCount() );
				entry.decrement();
				return false;
			}			
		}
		return true;
	}
	
	
	/*
	 * Remove a value from the context key
	 */
	public void remove(String contextKey, String value) {
		Map<String, ContextEntry> contextKeyMap = null;

		synchronized (mutex) {
			// Try to get the context key map
			contextKeyMap = entryCache.get(contextKey);
			if (contextKeyMap == null) {
				// Nothing more to do
				return;
			}
		}

		contextKeyMap.remove(value);
		LOG.debug("Cached value {} for key {} was removed from cache ", value,
				contextKey);
	}

	/*
	 * count some stats on the current cached context
	 */
	public List<ContextStats> getStats() {
		List<ContextStats> list = new ArrayList<ContextStats>();
		// synchronized the parsing of the key set to avoid adds during the
		// parsing
		synchronized (mutex) {
			for (String k : entryCache.keySet()) {
				list.add(new ContextStats(k, entryCache.get(k).size()));
			}
		}
		return list;
	}

	/*
	 * dump cache
	 */
	public Map<String, Map<String, ContextEntry>> dump() {
		return entryCache;
	}

	/*
	 * remove expired values from the cache olderThanTime : expressed in seconds
	 */
	public long removeExpiredContextEntry(long olderThanTime) {
		long nbRemovedObjects = 0L;

		// First, we duplicate the list of keys to allowed insertion during the
		// parsing of the key list
		TreeSet<String> keys = new TreeSet<String>(entryCache.keySet());

		// Parse each key to retrieve the associated Map
		for (String key : keys) {
			Map<String, ContextEntry> contextKey = entryCache.get(key);
			if (contextKey == null) {
				// Nothing more to do...
				continue;
			}

			// Build a sorted list based on expiration time
			List<Map.Entry<String, ContextEntry>> list = new LinkedList<Map.Entry<String, ContextEntry>>(
					contextKey.entrySet());

			// sort the list
			Collections.sort(list,
					new Comparator<Map.Entry<String, ContextEntry>>() {
						public int compare(Map.Entry<String, ContextEntry> o1,
								Map.Entry<String, ContextEntry> o2) {
							return (int) (o1.getValue().getExpirationtime() - o2
									.getValue().getExpirationtime());
						}
					});

			for (Iterator<Map.Entry<String, ContextEntry>> iter = list
					.iterator(); iter.hasNext();) {
				Map.Entry<String, ContextEntry> entry = (Map.Entry<String, ContextEntry>) iter
						.next();
				if (entry.getValue().getExpirationtime() > olderThanTime) {
					break;
				}
				if (LOG.isDebugEnabled()) {
					LOG.debug("**EXPIRED** Removing value " + entry.getKey()
							+ " from context key set identified by " + key);
				}
				contextKey.remove(entry.getKey());
				nbRemovedObjects++;
			}
		}

		// Return the number of removed objects
		return nbRemovedObjects;
	}

	public static void main(String[] args) {
		// Just for test...
		ContextEntryCache cache = ContextEntryCache.getInstance();
		// Generate a list of context entry
		List<ContextEntry> contextEntryList = new ArrayList<ContextEntry>();
		for (int j = 0; j < 20; j++) {
			for (int i = 0; i < 1000; i++) {
				ContextEntry ctx = new ContextEntry("key#" + j);
				ctx.setValue(String.valueOf(i));
				ctx.setExpirationtime(i);

				// System.out.println( "===> Adding " + ctx.getContextKey() +
				// "/" + ctx.getValue());
				contextEntryList.add(ctx);
			}
		}

		// shuffler the list
		Collections.shuffle(contextEntryList);

		// Add the randomized list to cache
		for (Iterator<ContextEntry> iter = contextEntryList.iterator(); iter
				.hasNext();) {
			ContextEntry ctx = iter.next();

			// System.out.println( "Adding in cache : key = " +
			// ctx.getContextKey() + "; value = " + ctx.getValue());

			cache.addElement(ctx);
		}

		class ConcurentInsert implements Runnable {

			private final String contextKey;
			private final ContextEntryCache cache = ContextEntryCache
					.getInstance();

			public ConcurentInsert(String contextKey) {
				this.contextKey = contextKey;
			}

			public void run() {
				int i = 0;
				while (true) {
					ContextEntry ctx = new ContextEntry(this.contextKey);
					ctx.setValue(String.valueOf(i));
					ctx.setExpirationtime(i);
					i++;

					// System.out.println( "====> Adding " + this.contextKey +
					// "/" + ctx.getValue());

					try {
						Thread.sleep(1);
					} catch (InterruptedException e) {
						return;
					}

					cache.addElement(ctx);
				}
			}
		}

		ThreadGroup tg = new ThreadGroup("Concurrent_injectors");
		for (int i = 0; i < 10; i++) {
			new Thread(tg, new ConcurentInsert("new#" + i)).start();
		}

		// Wait 5 seconds to see the logs
		try {
			Thread.sleep(5 * 1000);
		} catch (InterruptedException e1) {
			e1.printStackTrace();
		}

		System.out.println("===> Freeing context...");
		cache.removeExpiredContextEntry(500);
		System.out.println("===> Freeing context done.");

		// join all threads
		System.out.println("===> Interrupting threads...");
		tg.interrupt();
		System.out.println("===> All threads interrupted.");
		/*
		 * for( String key : cache.dump().keySet()) { Set<ContextEntry>
		 * contextValues = new TreeSet<ContextEntry>( new
		 * Comparator<ContextEntry>() { public int compare( ContextEntry o1,
		 * ContextEntry o2) { return (int)(o1.getExpirationtime() -
		 * o2.getExpirationtime()); } } ); contextValues.addAll(
		 * cache.dump().get(key).values()); for( ContextEntry e : contextValues)
		 * { System.out.println( "Still in cache : key = " + e.getContextKey() +
		 * "; value = " + e.getValue() + "; expiration = " +
		 * e.getExpirationtime()); } contextValues = null; }
		 */
	}

}
