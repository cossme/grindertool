#!/usr/bin/env python

import os
import json
import requests
import queue
import time
import random
import threading
import tornado.httpserver
import tornado.ioloop
from tornado import options
from tornadows import soaphandler
from tornadows import webservices
from tornadows import complextypes
from tornadows.soaphandler import webservice
import logging

#========== Avoid PROXY settings error =========
os.environ['NO_PROXY']='localhost,127.0.0.1,org.cossme.com'

#========== LOGGING =============
logger = logging.getLogger('productService')
logger.setLevel(logging.DEBUG)

class QueueReceiver:
	receiveQueue=queue.Queue()

	@classmethod
	def differedSending(cls):
# 		print ('[Thread=%s] Waiting' %  (threading.currentThread().getName()))
		while True :
			(productid,operationid,name,price,stock) = cls.receiveQueue.get()
			payload={"contextKey" :"operationid", "value":str(operationid), 
					"data": {"name":name,
							"price":price,
							"stock":stock,
							"productid": productid} 
					}
			logger.debug ('[operationid=%s] [productid=%s] payload=%s' % (str(operationid),productid,payload))
			sleep_time=random.randint(5,10)
			logger.debug ('[operationid=%s] [productid=%s] sleeping: %d seconds' % (str(operationid),productid, sleep_time))
			time.sleep(sleep_time)

			
			# Calling /update/context to give a feedback to contextManagement
			r = requests.post(URI, data = json.dumps(payload), headers = {'content-type': 'application/json'})
			if r.status_code in (500,502):
				logger.error('unset http_proxy and https_proxy to avoid issues related to proxy redirection OR set no_proxy !')
				r.raise_for_status()
				logger.debug ('[operationid=%s] [productid=%s] context/update calls done' % (str(operationid),productid))
			logger.debug ('[operationid=%s] [productid=%s] call to /updtate/context' % (str(operationid),productid))


class ProductDB:
	'''
	  A very simple memory DB (dictionary based)
	'''
	db = {1:('COMPUTER',1000.5,100),
	      2:('MOUSE',10.0,300),
	  	  3:('PENCIL BLUE',0.50,500),
	      4:('PENCIL RED',0.50,600),
	      5:('PENCIL WHITE',0.50,900),
	      6:('HEADPHONES',15.7,500),
	 }
	
	# to protect operation on dictionary
	lock=threading.Lock()
	
	productId=0
	
	@staticmethod
	def getDb():
		return ProductDB.db

	def __init__(self):
		self.__class__.productId=max(k for k in self.db.keys())

	@classmethod
	def get(cls, productId):
		row = (None,0.0,0)
		try:
			row = cls.db[productId]
		except:
			logger.error('Unable to find [productId=%d]' % (productId))
			raise 'Unable to find [productId=%d]' % (productId) 
		return row

	@classmethod
	def add(cls, name, price, stock):
		try:
			cls.lock.acquire()
			cls.productId+=1
			prodId=cls.productId
			cls.db[prodId] = (name,price,stock)
		finally:
			cls.lock.release()
		return prodId

#------------------------------------------------
# WS TYPES definition	
#------------------------------------------------
class Identifier(complextypes.ComplexType):
	idProduct = complextypes.IntegerProperty()

class Product(complextypes.ComplexType):
	id	= complextypes.IntegerProperty()
	name  = complextypes.StringProperty()
	price = complextypes.FloatProperty()
	stock = complextypes.IntegerProperty()
	
class AddedProduct(complextypes.ComplexType):
	operationid=complextypes.IntegerProperty()
	name  = complextypes.StringProperty()
	price = complextypes.FloatProperty()
	stock = complextypes.IntegerProperty()

#--------------------------------------------------
# Web services
#--------------------------------------------------
class ProductService(soaphandler.SoapHandler):
	# GLobal DB shared
	productDB = ProductDB()
	
	@webservice(_params=Identifier,_returns=Product)
	def getProduct(self, inputXml):
		productId = inputXml.idProduct.value	
		logger.info ('[productId=%s] getProduct CALLED' % (productId)	)
						
		reg = self.__class__.productDB.get(productId)
		output = Product()
		output.id.value	= productId
		output.name.value  = reg[0]
		output.price.value = reg[1]
		output.stock.value = reg[2]
		
		return output

	@webservice(_params=AddedProduct,_returns=Identifier)
	def addProduct(self, newProduct):
		logger.info ('[operationid=%s] addProduct CALLED' % (newProduct.operationid.value)	)
		identifier = Identifier()
		identifier.idProduct.value=self.__class__.productDB.add(newProduct.name.value,newProduct.price.value,newProduct.stock.value)
		QueueReceiver.receiveQueue.put((identifier.idProduct.value,
						                 newProduct.operationid.value,newProduct.name.value,newProduct.price.value,newProduct.stock.value))
		return identifier

	
if __name__ == '__main__':
	URI='http://localhost:9980/context/update'
	port=8889
	#---------------------------------------------
	service = [('ProductService',ProductService)]
	app = webservices.WebService(service)
	ws  = tornado.httpserver.HTTPServer(app)
	print ('Listening on port %d, ' % (port))
	print ('Callback URL: %s' % (URI))
	ws.listen(port)
	
	# Starting differed queue processing
	nbThread=50
	print ('Starting Threads [cound=%d] for differed sending' % (nbThread))
	for k in range(nbThread) :
# 		print ('count=%d' % (threading.activeCount())) 
		consumerThread = threading.Thread( target=QueueReceiver.differedSending, name='consumer %d' % (k))
		consumerThread.daemon = True
		consumerThread.start()
	
	# Main tornado loop
	try:
	    tornado.ioloop.IOLoop.instance().start()
	except KeyboardInterrupt:
	    tornado.ioloop.IOLoop.instance().stop()