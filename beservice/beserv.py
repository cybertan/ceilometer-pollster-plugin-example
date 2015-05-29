"""Common code for working with Backend Services
"""

from __future__ import absolute_import
import itertools

from oslo.config import cfg

from ceilometer.central import plugin
from ceilometer.openstack.common import timeutils
from ceilometer import sample
from ceilometer.openstack.common import log

import uuid
import os
import socket
import datetime

TARGET_SERVICES = {'cron':'a8a1fe3d-e770-4fa5-8ad0-5c2f145ef339',
				   'rsync':'fee48913-7752-4a6b-aa42-212cbd7c0db1'
				  }

LOG = log.getLogger(__name__)

class _Base(plugin.CentralPollster):
	@staticmethod
	def _get_servs():
		"""Returns a list of dicts describing all probes."""
		ip_addr = socket.gethostname()
		for serv in TARGET_SERVICES:
			serv_info = dict(id=TARGET_SERVICES[serv],
							serv_name=serv,
							node=ip_addr,
							curstat=_Base._check_stat(serv),
							timestamp=datetime.datetime.utcnow()
							)
			yield serv_info
	
	@staticmethod
	def _check_stat(serv):
		cmd_str = "service " + serv + " status"
		ret = os.popen(cmd_str).readlines()
		stat = None
		if str(ret[0]).find("not running") != -1:
			stat = 1  #stopped
		elif str(ret[0]).find("running") != -1:
			stat = 0  #running
		elif str(ret[0]).find("dead but pid file exists") != -1:
			stat = 3
		else:
			stat = 255
		return stat
	
	def _iter_servs(self, ksclient, cache):
		if 'servs' not in cache:
			cache['servs'] = list(self._get_servs())
		return iter(cache['servs'])
		
	@staticmethod
	def extract_serv_metadata(serv_info):
		return dict((k, serv_info[k])
					for k in
						[
						"id",
						"serv_name",
						"node",
						"timestamp"
						])
		
		#d = {"id":"example", "name":"servname", "node":"nodeIP", "timestamp":"currenttime"}
		#return d
		
	@staticmethod
	def check_serv_stat_trans(serv): 
		"""
			:param serv -- the qualified name of openstack service, such as "openstack-nova-scheduler"
			:return value:
				0 	-- no status changed => No event
				1 	-- service status transitioned from stopped into running => INFO event
				2 	-- service status transitioned from crashed into running => INFO event
				3 	-- service status transitioned from running into stopped => INFO event
				4 	-- service status transitioned from running into crashed => WARN event
				255 -- other transition
		"""
	
		TMP_FILE = '/tmp/serv_stat_opst'
		RUNNING = "running"
		STOPPED = "stopped"
		CRASHED = "crashed"
	
		# Obtain the service status from the last check
		# TBD. the content of the file should a hash with service name as key and status as value
		prev_stat = "unknown"
		if os.path.isfile(TMP_FILE):
			cmd = "cat " + TMP_FILE
			ret = os.popen(cmd).readlines()
			prev_stat = str(ret[0]).strip('\n')
		else:
			prev_stat = 'no stat'
	
		#obtain the specified service stat from the current check
		cur_stat = "unknown"
		cmd_str = "service " + serv + " status"
		ret = os.popen(cmd_str).readlines()
		print ret
		if str(ret[0]).find("is running") != -1:	
			cur_stat = RUNNING
		elif str(ret[0]).find("is stopped") != -1:
			cur_stat = STOPPED
		elif str(ret[0]).find("dead but pid file exists") != -1:
			cur_stat = CRASHED
		else: # should deal with the case of prev=="no stat"
			cur_stat = "others" # should be error, such as the specified service is not installed
	
		ret_val = 255
		if cur_stat == prev_stat:
			ret_val = 0
		else:
			#update current stat to TMP_FILE
			cmd_str = 'echo ' + cur_stat + '>' + TMP_FILE
			ret = os.popen(cmd_str).readlines()
		
			if (prev_stat == STOPPED) and (cur_stat == RUNNING):
				ret_val = 1
			elif (prev_stat == CRASHED) and (cur_stat == RUNNING):
				ret_val = 2
			elif (prev_stat == RUNNING) and (cur_stat == STOPPED):
				ret_val = 3
			elif (prev_stat == RUNNING) and (cur_stat == CRASHED):
				ret_val = 4
			else:
				ret_val = 255

		return ret_val
	
	@staticmethod
	def _get_servs_trans():
		ip_addr = socket.gethostname()
		for serv in TARGET_SERVICES:
			serv_info = dict(id=str(uuid.uuid4()),
							name=serv,
							node=ip_addr,
							stattrans=self.check_serv_stat_trans(serv)
							)
			yield serv_info
	
	def _iter_servs_trans(self, ksclient, cache):
		if 'servs' not in cache:
			cache['servs'] = list(self._get_servs_trans())
		return iter(cache['servs'])
	
class ServStatPollster(_Base):
    """Measures service status."""
    @plugin.check_keystone
    def get_samples(self, manager, cache, resources=None):
        """Returns all samples."""
        for probe in self._iter_servs(None, cache):
            yield sample.Sample(
                name='service.stat',
                type=sample.TYPE_GAUGE,
                unit='service', #TBD no meaning
                volume=probe['curstat'],
                user_id="932bf67dd600425aa99873cf58fda988",
                project_id="cb49d4549ebb4fe097018aa7f8dd27f6",
                resource_id=probe['id'],
                #timestamp=datetime.datetime.fromtimestamp(
                #    probe['timestamp']).isoformat(),
				timestamp=probe['timestamp'].isoformat(),
                resource_metadata=self.extract_serv_metadata(probe)
            )

class ServStatTransPollster(_Base):
    """Measures service status transition."""
    @plugin.check_keystone
    def get_samples(self, manager, cache, resources=None):
        """Returns all samples."""
        for probe in self._iter_servs_trans(manager.keystone, cache):
            yield sample.Sample(
                name='service.transition',
                type=sample.TYPE_GAUGE,
                unit='S', #TBD no meaning
                volume=probe['stattrans'],
                user_id=None,
                project_id=None,
                resource_id=probe['id'],
                #timestamp=datetime.datetime.fromtimestamp(
                #    probe['timestamp']).isoformat(),
				timestamp=probe['timestamp'].isoformat(),
                resource_metadata=self.extract_serv_metadata(probe)
            )
"""
	for testing
"""
def main():
	print "testing _iter_servs()..."
	tt = ServStatPollster()
	print list(tt._iter_servs(None, {}))
	
	print "############"
	for probe in tt._iter_servs(None, {}):
		print type(probe)
		print probe
	
	print "ServStatPollster get_samples testing..."
	manager=None
	sams = tt.get_samples(manager, {})
	print type(sams)
	for a in sams:
		print type(a)
		print a.volume
		print a.resource_metadata['serv_name']
	
	for sam in ServStatPollster().get_samples(manager, {}):
		print sam.timestamp
		
if __name__ == "__main__":
	main()			
	