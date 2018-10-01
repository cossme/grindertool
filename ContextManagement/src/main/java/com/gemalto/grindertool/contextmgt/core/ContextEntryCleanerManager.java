package org.cossme.grindertool.contextmgt.core;

import io.dropwizard.lifecycle.Managed;

import java.util.concurrent.atomic.AtomicLong;

import com.codahale.metrics.Counter;
import com.codahale.metrics.Gauge;
import com.codahale.metrics.MetricRegistry;


/*
 * This class is in charge of starting a thread within the application lifecycle.
 * There is one thread per ContextEntryCleanerManager object. This object is intended to be instantiated only one time.
 * This Thread is in charge of removing all expired context entry.
 */
public class ContextEntryCleanerManager implements Managed, Runnable {
	// Defines the name of the thread
	private static final String THREAD_NAME = "ContextEntry_Cleaner_Thread";
	
	// Defines the delay between two run of the cleaner thread
	private static final long THREAD_SLEEP_TIME = 30*1000; // Thread wakes up every 30s
	
	// Will hold the reference of the instantiated Thread
	private final Thread cleanerThread;
	
	// Will hold the reference of the metrics framework
	private final MetricRegistry metricsRegistry;
	
	// Flag used to stop properly the thread between 2 run
	private boolean running = true;
	
	// counter sections
	private AtomicLong nbRemovedObjectByReaper = new AtomicLong(0L);
	private AtomicLong reaperDurationByReaper = new AtomicLong(0L);
	
	private final Gauge<Long> nbRemovedGauge = new Gauge<Long>() {
        public Long getValue() {
            return nbRemovedObjectByReaper.get();
        }
    };
	private final Counter reaperRunningCount = new Counter();
	private final Gauge<Long> reaperDurationGauge = new Gauge<Long>() {
        public Long getValue() {
            return reaperDurationByReaper.get();
        }
    };
	
    
	// Constructor that create the Thread and point to the cleaner itself.
	public ContextEntryCleanerManager( MetricRegistry metrics) {
	  this.cleanerThread = new Thread( this, ContextEntryCleanerManager.THREAD_NAME);
	  this.metricsRegistry = metrics;
	  
	  // Register the gauge that maintains the number of removed objects done by the cleaner thread
	  metrics.register( MetricRegistry.name( this.getClass(), "reaper", "removed"), this.nbRemovedGauge);
	  // Register the nb of running reaper since the beginning
	  metrics.register( MetricRegistry.name( this.getClass(), "reaper", "runs"), this.reaperRunningCount);
	  // Register the reaper duration
	  metrics.register( MetricRegistry.name( this.getClass(), "reaper", "duration"), this.reaperDurationGauge);	  
	}

	// Start the thread
	public void start() throws Exception {
		this.cleanerThread.start();
	}

	// Stop the thread
	public void stop() throws Exception {
		// Inform the thread to stop
		this.running = false;
		// Wait 5 seconds for the thread to die
		this.cleanerThread.join( 5*1000);
		// If the thread is still alive then interrupt it
		if ( this.cleanerThread.isAlive()) {
		    this.cleanerThread.interrupt();
		}
	}

	// Loop until the thread is interrupted and proccessed a cleaning job with a
	// specific interval
	public void run() {
		while( running) {
			try {
				Thread.sleep( ContextEntryCleanerManager.THREAD_SLEEP_TIME);
			} catch (InterruptedException e) {
				return; // Nothing more to do except to die.				
			}
			
			// Do here the cleaning job
			doCleaningJob();
		}
	}
	
	// The implementation of the cleaning job
	private void doCleaningJob()
	{
		// increment the nb of run
		this.reaperRunningCount.inc();
		
		// memorize starting time
		long startTime = System.currentTimeMillis();
		
		// Get the instance of the cache, and remove all expired requests
		this.nbRemovedObjectByReaper.set( ContextEntryCache.getInstance().removeExpiredContextEntry( startTime - 30000));
		
		// Compute the execution time in ms
		this.reaperDurationByReaper.set( System.currentTimeMillis()-startTime);
	}
	
}
