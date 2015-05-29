#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

"""
	REST Interface for Cloud Device Manager
"""
import requests
import json
import hashlib

class CeiloClient:
	# authorization config
	username = "admin"
	password = "iforgot"
	projectid = "cb49d4549ebb4fe097018aa7f8dd27f6"  # Tenant ID for "admin"
	auth_url = "http://10.103.0.168:5000/v2.0/tokens"  # Keystone token endpoint
	
	def __init__(self):
		#list attributes
		self.ceilo_headers = None
		self.ceilo_endpoint = None
		
		# format token request and json encode
		data = {"auth":{}}
		data["auth"]["passwordCredentials"] = {
			"username":self.username,
			"password":self.password
			}
		data["auth"]["tenantId"] = self.projectid
		data = json.dumps(data)
	
		#create request headers
		headers = {
			'content-type':'application/json',
			'accept':'application/json',
			}
	
		#request authorization token from keystone
		ret = requests.post(self.auth_url, data=data, headers=headers)
		if not ret.status_code == 200:
			raise Exception

		#parse token response
		token_id = ret.json()['access']['token']['id']

		#parse ceilometer endpoint
		for endpoint in ret.json()['access']['serviceCatalog']:
			if endpoint['name'] == 'ceilometer':
				self.ceilo_endpoint = endpoint['endpoints'][0]['publicURL']
				break
		if self.ceilo_endpoint == "":
			print "no endpoint of ceilometer found"
			raise Exception

		# set tokenized headers
		self.ceilo_headers = {'X-Auth-Token':token_id}
		
	def get_meters(self):
		ret = requests.get("%s/v2/meters" % self.ceilo_endpoint, headers=self.ceilo_headers)
		if not ret.status_code == 200:
			print "get meters failed and staus code is %s" % ret.status_code
			raise Exception
		
		#print ret.text
		text_obj = json.loads(ret.text)
		for meter in text_obj:
			print meter['name']
			
	
	def get_alarms(self):
		ret = requests.get("%s/v2/alarms" % self.ceilo_endpoint, headers=self.ceilo_headers)
		if not ret.status_code == 200:
			print "get meters failed"
			raise Exception
		
		print "statuscode: %s" % ret.status_code
		print ret.headers['content-type']
		print ret.encoding
		print ret.text	
		

def main():
	ceiloClient = CeiloClient()
	ceiloClient.get_meters()
		
		
if __name__ == "__main__":
	main()
