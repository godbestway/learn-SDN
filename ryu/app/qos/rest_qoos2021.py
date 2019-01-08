# Copyright (C) 2014 Kiyonari Harigae <lakshmi at cloudysunny14 org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import logging
import json
import re

from ryu.app import conf_switch_key as cs_key
from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import Response
from ryu.app.wsgi import route
from ryu.app.wsgi import WSGIApplication
from ryu.base import app_manager
from ryu.controller import conf_switch
from ryu.controller import ofp_event
from ryu.controller import dpset
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.exception import OFPUnknownVersion
from ryu.lib import dpid as dpid_lib
from ryu.lib import mac
from ryu.lib import ofctl_v1_0
from ryu.lib import ofctl_v1_2
from ryu.lib import ofctl_v1_3
from ryu.lib.ovs import bridge
from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ofproto_v1_3_parser
from ryu.ofproto import ether
from ryu.ofproto import inet

from ryu.controller import ofp_event
import threading
import time
import copy 
# =============================
#          REST API
# =============================
#
#  Note: specify switch and vlan group, as follows.
#   {switch-id} : 'all' or switchID
#   {vlan-id}   : 'all' or vlanID
#
# about queue status
#
# get status of queue
# GET /qos/queue/status/{switch-id}
#
# about queues
# get a queue configurations
# GET /qos/queue/{switch-id}
#
# set a queue to the switches
# POST /qos/queue/{switch-id}
#
# request body format:
#  {"port_name":"<name of port>",
#   "type": "<linux-htb or linux-other>",
#   "max-rate": "<int>",
#   "queues":[{"max_rate": "<int>", "min_rate": "<int>"},...]}
#
#   Note: This operation override
#         previous configurations.
#   Note: Queue configurations are available for
#         OpenvSwitch.
#   Note: port_name is optional argument.
#         If does not pass the port_name argument,
#         all ports are target for configuration.
#
# delete queue
# DELETE /qos/queue/{swtich-id}
#
#   Note: This operation delete relation of qos record from
#         qos colum in Port table. Therefore,
#         QoS records and Queue records will remain.
#
# about qos rules
#
# get rules of qos
# * for no vlan
# GET /qos/rules/{switch-id}
#
# * for specific vlan group
# GET /qos/rules/{switch-id}/{vlan-id}
#
# set a qos rules
#
#   QoS rules will do the processing pipeline,
#   which entries are register the first table (by default table id 0)
#   and process will apply and go to next table.
#
# * for no vlan
# POST /qos/{switch-id}
#
# * for specific vlan group
# POST /qos/{switch-id}/{vlan-id}
#
#  request body format:
#   {"priority": "<value>",
#    "match": {"<field1>": "<value1>", "<field2>": "<value2>",...},
#    "actions": {"<action1>": "<value1>", "<action2>": "<value2>",...}
#   }
#
#  Description
#    * priority field
#     <value>
#    "0 to 65533"
#
#   Note: When "priority" has not been set up,
#         "priority: 1" is set to "priority".
#
#    * match field
#     <field> : <value>
#    "in_port" : "<int>"
#    "dl_src"  : "<xx:xx:xx:xx:xx:xx>"
#    "dl_dst"  : "<xx:xx:xx:xx:xx:xx>"
#    "dl_type" : "<ARP or IPv4 or IPv6>"
#    "nw_src"  : "<A.B.C.D/M>"
#    "nw_dst"  : "<A.B.C.D/M>"
#    "ipv6_src": "<xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/M>"
#    "ipv6_dst": "<xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx/M>"
#    "nw_proto": "<TCP or UDP or ICMP or ICMPv6>"
#    "tp_src"  : "<int>"
#    "tp_dst"  : "<int>"
#    "ip_dscp" : "<int>"
#
#    * actions field
#     <field> : <value>
#    "mark": <dscp-value>
#    sets the IPv4 ToS/DSCP field to tos.
#    "meter": <meter-id>
#    apply meter entry
#    "queue": <queue-id>
#    register queue specified by queue-id
#
#   Note: When "actions" has not been set up,
#         "queue: 0" is set to "actions".
#
# delete a qos rules
# * for no vlan
# DELETE /qos/rule/{switch-id}
#
# * for specific vlan group
# DELETE /qos/{switch-id}/{vlan-id}
#
#  request body format:
#   {"<field>":"<value>"}
#
#     <field>  : <value>
#    "qos_id" : "<int>" or "all"
#
# about meter entries
#
# set a meter entry
# POST /qos/meter/{switch-id}
#
#  request body format:
#   {"meter_id": <int>,
#    "bands":[{"action": "<DROP or DSCP_REMARK>",
#              "flag": "<KBPS or PKTPS or BURST or STATS"
#              "burst_size": <int>,
#              "rate": <int>,
#              "prec_level": <int>},...]}
#
# delete a meter entry
# DELETE /qos/meter/{switch-id}
#
#  request body format:
#   {"<field>":"<value>"}
#
#     <field>  : <value>
#    "meter_id" : "<int>"
#


SWITCHID_PATTERN = dpid_lib.DPID_PATTERN + r'|all'
VLANID_PATTERN = r'[0-9]{1,4}|all'

QOS_TABLE_ID = 0

REST_ALL = 'all'
REST_SWITCHID = 'switch_id'
REST_COMMAND_RESULT = 'command_result'
REST_PRIORITY = 'priority'
REST_QUEUE_PRIORITY = 'queue_priority'
REST_VLANID = 'vlan_id'
REST_PORT_NAME = 'port_name'
REST_QUEUE_TYPE = 'type'
REST_QUEUE_MAX_RATE = 'max_rate'
REST_QUEUE_MIN_RATE = 'min_rate'
REST_QUEUES = 'queues'
REST_QOS = 'qos'
REST_QOS_ID = 'qos_id'
REST_COOKIE = 'cookie'

REST_MATCH = 'match'
REST_IN_PORT = 'in_port'
REST_SRC_MAC = 'dl_src'
REST_DST_MAC = 'dl_dst'
REST_DL_TYPE = 'dl_type'
REST_DL_TYPE_ARP = 'ARP'
REST_DL_TYPE_IPV4 = 'IPv4'
REST_DL_TYPE_IPV6 = 'IPv6'
REST_DL_VLAN = 'dl_vlan'
REST_SRC_IP = 'nw_src'
REST_DST_IP = 'nw_dst'
REST_SRC_IPV6 = 'ipv6_src'
REST_DST_IPV6 = 'ipv6_dst'
REST_NW_PROTO = 'nw_proto'
REST_NW_PROTO_TCP = 'TCP'
REST_NW_PROTO_UDP = 'UDP'
REST_NW_PROTO_ICMP = 'ICMP'
REST_NW_PROTO_ICMPV6 = 'ICMPv6'
REST_TP_SRC = 'tp_src'
REST_TP_DST = 'tp_dst'
REST_DSCP = 'ip_dscp'

REST_ACTION = 'actions'
REST_ACTION_QUEUE = 'queue'
REST_ACTION_MARK = 'mark'
REST_ACTION_METER = 'meter'

REST_METER_ID = 'meter_id'
REST_METER_BURST_SIZE = 'burst_size'
REST_METER_RATE = 'rate'
REST_METER_PREC_LEVEL = 'prec_level'
REST_METER_BANDS = 'bands'
REST_METER_ACTION_DROP = 'drop'
REST_METER_ACTION_REMARK = 'remark'

DEFAULT_FLOW_PRIORITY = 0
QOS_PRIORITY_MAX = ofproto_v1_3_parser.UINT16_MAX - 1
QOS_PRIORITY_MIN = 1

VLANID_NONE = 0
VLANID_MIN = 2
VLANID_MAX = 4094
COOKIE_SHIFT_VLANID = 32
REST_TIME = 'time'
BASE_URL = '/qos'
REQUIREMENTS = {'switchid': SWITCHID_PATTERN,
                'vlanid': VLANID_PATTERN}

LOG = logging.getLogger(__name__)
selfqueue_list = {}
selfovsdb_addr = None
selfovs_bridge = None
selfqos_list = []
timer = None
selfqueues_single = []
last_queues = []
outside_waiters = None
change = None
first_time = False
last_port_stats = []


class RestQoSAPI(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION,
                    ofproto_v1_2.OFP_VERSION,
                    ofproto_v1_3.OFP_VERSION]

    _CONTEXTS = {
        'dpset': dpset.DPSet,
        'conf_switch': conf_switch.ConfSwitchSet,
        'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(RestQoSAPI, self).__init__(*args, **kwargs)

        # logger configure
        QoSController.set_logger(self.logger)
        self.cs = kwargs['conf_switch']
        self.dpset = kwargs['dpset']
        wsgi = kwargs['wsgi']
        self.waiters = {}
        self.data = {}
        self.data['dpset'] = self.dpset
        self.data['waiters'] = self.waiters
        wsgi.registory['QoSController'] = self.data
        wsgi.register(QoSController, self.data)
    
    def stats_reply_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath

        if dp.id not in self.waiters:
            return
        if msg.xid not in self.waiters[dp.id]:
            return
        lock, msgs = self.waiters[dp.id][msg.xid]
        msgs.append(msg)

        flags = 0
        if dp.ofproto.OFP_VERSION == ofproto_v1_0.OFP_VERSION or \
                dp.ofproto.OFP_VERSION == ofproto_v1_2.OFP_VERSION:
            flags = dp.ofproto.OFPSF_REPLY_MORE
        elif dp.ofproto.OFP_VERSION == ofproto_v1_3.OFP_VERSION:
            flags = dp.ofproto.OFPMPF_REPLY_MORE

        if msg.flags & flags:
            return
        del self.waiters[dp.id][msg.xid]
        lock.set()

    @set_ev_cls(conf_switch.EventConfSwitchSet)
    def conf_switch_set_handler(self, ev):
        if ev.key == cs_key.OVSDB_ADDR:
            QoSController.set_ovsdb_addr(ev.dpid, ev.value)
        else:
            QoSController._LOGGER.debug("unknown event: %s", ev)

    @set_ev_cls(conf_switch.EventConfSwitchDel)
    def conf_switch_del_handler(self, ev):
        if ev.key == cs_key.OVSDB_ADDR:
            QoSController.delete_ovsdb_addr(ev.dpid)
        else:
            QoSController._LOGGER.debug("unknown event: %s", ev)

    @set_ev_cls(dpset.EventDP, dpset.DPSET_EV_DISPATCHER)
    def handler_datapath(self, ev):
        if ev.enter:
            QoSController.regist_ofs(ev.dp, self.CONF)
        else:
            QoSController.unregist_ofs(ev.dp)

    # for OpenFlow version1.0
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def stats_reply_handler_v1_0(self, ev):
        self.stats_reply_handler(ev)

    # for OpenFlow version1.2 or later
    @set_ev_cls(ofp_event.EventOFPStatsReply, MAIN_DISPATCHER)
    def stats_reply_handler_v1_2(self, ev):
        self.stats_reply_handler(ev)

    # for OpenFlow version1.2 or later
    @set_ev_cls(ofp_event.EventOFPQueueStatsReply, MAIN_DISPATCHER)
    def queue_stats_reply_handler_v1_2(self, ev):
        self.stats_reply_handler(ev)

    # for OpenFlow version1.2 or later
    @set_ev_cls(ofp_event.EventOFPMeterStatsReply, MAIN_DISPATCHER)
    def meter_stats_reply_handler_v1_2(self, ev):
        self.stats_reply_handler(ev)


class QoSOfsList(dict):

    def __init__(self):
        super(QoSOfsList, self).__init__()
    
    def get_ofs(self, dp_id):
        if len(self) == 0:
            raise ValueError('qos sw is not connected.')

        dps = {}
        if dp_id == REST_ALL:
            dps = self
        else:
            try:
                dpid = dpid_lib.str_to_dpid(dp_id)
            except:
                raise ValueError('Invalid switchID.')

            if dpid in self:
                dps = {dpid: self[dpid]}
            else:
                msg = 'qos sw is not connected. : switchID=%s' % dp_id
                raise ValueError(msg)

        return dps


class QoSController(ControllerBase):

    _OFS_LIST = QoSOfsList()
    _LOGGER = None

    def __init__(self, req, link, data, **config):
        super(QoSController, self).__init__(req, link, data, **config)
        self.dpset = data['dpset']
        self.waiters = data['waiters']
    
    @classmethod
    def set_logger(cls, logger):
        cls._LOGGER = logger
        cls._LOGGER.propagate = False
        hdlr = logging.StreamHandler()
        fmt_str = '[QoS][%(levelname)s] %(message)s'
        hdlr.setFormatter(logging.Formatter(fmt_str))
        cls._LOGGER.addHandler(hdlr)
    
    @staticmethod
    def regist_ofs(dp, CONF):
        if dp.id in QoSController._OFS_LIST:
            return

        dpid_str = dpid_lib.dpid_to_str(dp.id)
        try:
            f_ofs = QoS(dp, CONF)
            f_ofs.set_default_flow()
        except OFPUnknownVersion as message:
            QoSController._LOGGER.info('dpid=%s: %s',
                                       dpid_str, message)
            return

        QoSController._OFS_LIST.setdefault(dp.id, f_ofs)
        QoSController._LOGGER.info('dpid=%s: Join qos switch.',
                                   dpid_str)

    @staticmethod
    def unregist_ofs(dp):
        if dp.id in QoSController._OFS_LIST:
            del QoSController._OFS_LIST[dp.id]
            QoSController._LOGGER.info('dpid=%s: Leave qos switch.',
                                       dpid_lib.dpid_to_str(dp.id))
    
    @staticmethod
    def set_ovsdb_addr(dpid, value):
        ofs = QoSController._OFS_LIST.get(dpid, None)
        if ofs is not None:
            ofs.set_ovsdb_addr(dpid, value)

    @staticmethod
    def delete_ovsdb_addr(dpid):
        ofs = QoSController._OFS_LIST.get(dpid, None)
        if ofs is not None:
            ofs.set_ovsdb_addr(dpid, None)


    @route('qos_switch', BASE_URL + '/rules/{switchid}', methods=['PUT'], requirements=REQUIREMENTS)
    def put_rules(self,req, switchid, **_kwargs):
    	return self._access_switch(req, switchid, VLANID_NONE, 'put_rules', self.waiters)

    
    @route('qos_switch', BASE_URL + '/queue/{switchid}',
           methods=['GET'], requirements=REQUIREMENTS)
    def get_queue(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'get_queue', None)

    @route('qos_switch', BASE_URL + '/queue/{switchid}',
           methods=['POST'], requirements=REQUIREMENTS)
    def set_queue(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'set_queue', None)

    @route('qos_switch', BASE_URL + '/queue/{switchid}',
           methods=['DELETE'], requirements=REQUIREMENTS)
    def delete_queue(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'delete_queue', None)

    @route('qos_switch', BASE_URL + '/queue/status/{switchid}',
           methods=['GET'], requirements=REQUIREMENTS)
    def get_status(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'get_status', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}',
           methods=['GET'], requirements=REQUIREMENTS)
    def get_qos(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'get_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}/{vlanid}',
           methods=['GET'], requirements=REQUIREMENTS)
    def get_vlan_qos(self, req, switchid, vlanid, **_kwargs):
        return self._access_switch(req, switchid, vlanid,
                                   'get_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}',
           methods=['POST'], requirements=REQUIREMENTS)
    def set_qos(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'set_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}/{vlanid}',
           methods=['POST'], requirements=REQUIREMENTS)
    def set_vlan_qos(self, req, switchid, vlanid, **_kwargs):
        return self._access_switch(req, switchid, vlanid,
                                   'set_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}',
           methods=['DELETE'], requirements=REQUIREMENTS)
    def delete_qos(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'delete_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/rules/{switchid}/{vlanid}',
           methods=['DELETE'], requirements=REQUIREMENTS)
    def delete_vlan_qos(self, req, switchid, vlanid, **_kwargs):
        return self._access_switch(req, switchid, vlanid,
                                   'delete_qos', self.waiters)

    @route('qos_switch', BASE_URL + '/meter/{switchid}',
           methods=['GET'], requirements=REQUIREMENTS)
    def get_meter(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'get_meter', self.waiters)

    @route('qos_switch', BASE_URL + '/meter/{switchid}',
           methods=['POST'], requirements=REQUIREMENTS)
    def set_meter(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'set_meter', self.waiters)

    @route('qos_switch', BASE_URL + '/meter/{switchid}',
           methods=['DELETE'], requirements=REQUIREMENTS)
    def delete_meter(self, req, switchid, **_kwargs):
        return self._access_switch(req, switchid, VLANID_NONE,
                                   'delete_meter', self.waiters)
    
    def _access_switch(self, req, switchid, vlan_id, func, waiters):
        try:
            rest = req.json if req.body else {}
        except ValueError:
            QoSController._LOGGER.debug('invalid syntax %s', req.body)
            return Response(status=400)

        try:
            dps = self._OFS_LIST.get_ofs(switchid)
            vid = QoSController._conv_toint_vlanid(vlan_id)
        except ValueError as message:
            return Response(status=400, body=str(message))

        msgs = []
        for f_ofs in dps.values():
            function = getattr(f_ofs, func)
            try:
                if waiters is not None:
                    msg = function(rest, vid, waiters)
                else:
                    msg = function(rest, vid)
            except ValueError as message:
                return Response(status=400, body=str(message))
            msgs.append(msg)

        body = json.dumps(msgs)
        return Response(content_type='application/json', body=body)

    @staticmethod
    def _conv_toint_vlanid(vlan_id):
        if vlan_id != REST_ALL:
            vlan_id = int(vlan_id)
            if (vlan_id != VLANID_NONE and
                    (vlan_id < VLANID_MIN or VLANID_MAX < vlan_id)):
                msg = 'Invalid {vlan_id} value. Set [%d-%d]' % (VLANID_MIN,
                                                                VLANID_MAX)
                raise ValueError(msg)
        return vlan_id


class QoS(object):

    _OFCTL = {ofproto_v1_0.OFP_VERSION: ofctl_v1_0,
              ofproto_v1_2.OFP_VERSION: ofctl_v1_2,
              ofproto_v1_3.OFP_VERSION: ofctl_v1_3}

    def __init__(self, dp, CONF):
        super(QoS, self).__init__()
        self.vlan_list = {}
        self.vlan_list[VLANID_NONE] = 0  # for VLAN=None
        self.dp = dp
        self.version = dp.ofproto.OFP_VERSION
        # Dictionary of port name to Queue config.
        # e.g.)
        # self.queue_list = {
        #     "s1-eth1": {
        #         "0": {
        #             "config": {
        #                 "max-rate": "600000"
        #             }
        #         },
        #         "1": {
        #             "config": {
        #                 "min-rate": "900000"
        #             }
        #         }
        #     }
        # }
#        self.queue_list = {}
        self.CONF = CONF
#        selfovsdb_addr = None
#        selfovs_bridge = None
        global selfqueue_list
        global selfovsdb_addr
        global selfovs_bridge
        global selfqueues_single
	global last_queues

        self.restQueue_muster = {REST_PORT_NAME:"" , REST_QUEUE_TYPE:"linux-htb" , REST_QUEUE_MAX_RATE:"1000000" , REST_QUEUES:[]}        
        self.rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:""}
        self.rest_action = {REST_ACTION_QUEUE:""}
        self.restQos_muster = {REST_QUEUE_PRIORITY:"0", REST_MATCH:self.rest_match , REST_ACTION:self.rest_action}
        
        if self.version not in self._OFCTL:
            raise OFPUnknownVersion(version=self.version)

        self.ofctl = self._OFCTL[self.version]

    def set_default_flow(self):
        if self.version == ofproto_v1_0.OFP_VERSION:
            return

        cookie = 0
        priority = DEFAULT_FLOW_PRIORITY
        actions = [{'type': 'GOTO_TABLE',
                    'table_id': QOS_TABLE_ID + 1}]
        flow = self._to_of_flow(cookie=cookie,
                                priority=priority,
                                match={},
                                actions=actions)

        cmd = self.dp.ofproto.OFPFC_ADD
        self.ofctl.mod_flow_entry(self.dp, flow, cmd)




    def set_ovsdb_addr(self, dpid, ovsdb_addr):
        global selfovsdb_addr
        global selfovs_bridge
        old_address = selfovsdb_addr
        if old_address == ovsdb_addr:
            return
        elif ovsdb_addr is None:
            # Determine deleting OVSDB address was requested.
            if selfovs_bridge:
               selfovs_bridge = None
            return
        ovs_bridge = bridge.OVSBridge(self.CONF, dpid, ovsdb_addr)
        try:
            ovs_bridge.init()
        except:
            raise ValueError('ovsdb addr is not available.')
        selfovsdb_addr = ovsdb_addr
        selfovs_bridge = ovs_bridge

    def _update_vlan_list(self, vlan_list):
        for vlan_id in self.vlan_list.keys():
            if vlan_id is not VLANID_NONE and vlan_id not in vlan_list:
                del self.vlan_list[vlan_id]

    def _get_cookie(self, vlan_id):
        if vlan_id == REST_ALL:
            vlan_ids = self.vlan_list.keys()
        else:
            vlan_ids = [vlan_id]

        cookie_list = []
        for vlan_id in vlan_ids:
            self.vlan_list.setdefault(vlan_id, 0)
            self.vlan_list[vlan_id] += 1
            self.vlan_list[vlan_id] &= ofproto_v1_3_parser.UINT32_MAX
            cookie = (vlan_id << COOKIE_SHIFT_VLANID) + \
                self.vlan_list[vlan_id]
            cookie_list.append([cookie, vlan_id])

        return cookie_list

    @staticmethod
    def _cookie_to_qosid(cookie):
        return cookie & ofproto_v1_3_parser.UINT32_MAX

    # REST command template
    def rest_command(func):
        def _rest_command(*args, **kwargs):
            key, value = func(*args, **kwargs)
            switch_id = dpid_lib.dpid_to_str(args[0].dp.id)
            return {REST_SWITCHID: switch_id,
                    key: value}
        return _rest_command

    @rest_command
    def get_status(self, req, vlan_id, waiters):
        if self.version == ofproto_v1_0.OFP_VERSION:
            raise ValueError('get_status operation is not supported')

        msgs = self.ofctl.get_queue_stats(self.dp, waiters)
        return REST_COMMAND_RESULT, msgs

    @rest_command
    def get_queue(self, rest, vlan_id):
        global selfqueue_list
        if len(selfqueue_list):
            msg = {'result': 'success',
                   'details': selfqueue_list}
        else:
            msg = {'result': 'failure',
                   'details': 'Queue is not exists.'}

        return REST_COMMAND_RESULT, msg

    @rest_command
    def set_queue(self, rest, vlan_id):
        global selfovs_bridge
        if selfovs_bridge is None:
            msg = {'result': 'failure',
                   'details': 'ovs_bridge is not exists'}
            return REST_COMMAND_RESULT, msg

        port_name = rest.get(REST_PORT_NAME, None)
        vif_ports = selfovs_bridge.get_port_name_list()

        if port_name is not None:
            if port_name not in vif_ports:
                raise ValueError('%s port is not exists' % port_name)
            vif_ports = [port_name]

        queue_list = {}
        queue_type = rest.get(REST_QUEUE_TYPE, 'linux-htb')
        parent_max_rate = rest.get(REST_QUEUE_MAX_RATE, None)
        queues = rest.get(REST_QUEUES, [])
        queue_id = 0
        queue_config = []
        for queue in queues:
            max_rate = queue.get(REST_QUEUE_MAX_RATE, None)
            min_rate = queue.get(REST_QUEUE_MIN_RATE, None)
            if max_rate is None and min_rate is None:
                raise ValueError('Required to specify max_rate or min_rate')
            config = {}
            if max_rate is not None:
                config['max-rate'] = max_rate
            if min_rate is not None:
                config['min-rate'] = min_rate
            if len(config):
                queue_config.append(config)
            queue_list[queue_id] = {'config': config}
            queue_id += 1

        for port_name in vif_ports:
            try:
                selfovs_bridge.set_qos(port_name, type=queue_type,
                                        max_rate=parent_max_rate,
                                        queues=queue_config)
            except Exception as msg:
                raise ValueError(msg)
            selfqueue_list[port_name] = queue_list

        msg = {'result': 'success',
               'details': queue_list}

        return REST_COMMAND_RESULT, msg




    @rest_command
    def put_rules(self, rest, vlan_id, waiters):         
        global selfqos_list
        global selfqueue_list
        #global selfqueues_single
        #global timer 
	global last_queues
	global outside_waiters
	global change
        global first_time
        global last_port_stats
	outside_waiters = waiters
        
	if first_time == False:
           last_port_stats = self.get_port_stats()
           self.request_flow_stats() 
	
	match_value = rest[REST_MATCH]
        port = match_value[REST_TP_DST]
	action_value = rest.get(REST_ACTION)
	action_value_keys = action_value.keys()

        print rest
	
	priority = rest[REST_QUEUE_PRIORITY]
	come_max_rate=action_value.get(REST_QUEUE_MAX_RATE)
	come_min_rate=action_value.get(REST_QUEUE_MIN_RATE)
	
	
	new_restQueue , regular_queues = self.develop_regular_queues(port, priority, come_min_rate, come_max_rate)
        
        print new_restQueue , "------" , regular_queues

	last_queues = regular_queues

        advanced_queues = self.develop_advanced_queues(regular_queues)
	new_restQueue[REST_QUEUES] = advanced_queues
	
	msg=[port, selfqueue_list , selfqos_list]
	print msg , "----" , priority
	self.set_queue_forAll(new_restQueue , selfqos_list , 0 , waiters)
#        mm = self.ofctl.get_flow_stats(self.dp , outside_waiters)
	return REST_COMMAND_RESULT, [last_port_stats]
	
    
     #sum_max_rate = 1000000
     #left_max_rate = 0
    def init_o




    def develop_regular_queues(self, port , priority , come_min_rate, come_max_rate):
    	global selfqos_list
        global selfqueue_list
        #global selfqueues_single
        #global timer 
	global last_queues
	global outside_waiters
	global change
        #global first_time
        #global last_port_stats
	
	new_queue_list = {}
	new_queue_list=copy.deepcopy(selfqueue_list)
	
	key = new_queue_list.keys()
	string_key=key[-1]
	queue= {}

	queue = new_queue_list[string_key]
	queue_keys = queue.keys()
	new_key =  int(queue_keys[-1])+1
	parent_max_rate = self.restQueue_muster[REST_QUEUE_MAX_RATE]

	#change "max or min rate" form queue_list into rest_form
	queues = []
	original_port_rate = []
	"""
	for k in queue.keys():
		config_value = queue[k]["config"]
	        config_value_key_list=config_value.keys()
	        if config_value_key_list[0] == "max-rate":
	        	max_rate = str(config_value["max-rate"])
		        new_dict = {}
			new_dict[REST_QUEUE_MAX_RATE] = max_rate
			queues.append(new_dict)
		
		elif config_value_key_list[0] == "min-rate":
		        min_rate = str(config_value["min-rate"])
		        new_dict = {}
			new_dict[REST_QUEUE_MIN_RATE] = min_rate
			queues.append(new_dict)
			
		else:
			pass
	"""
	
	if come_min_rate != None:
		queues.append({REST_QUEUE_MIN_RATE:come_min_rate})
	else:
		queues.append({REST_QUEUE_MAX_RATE:come_max_rate})

        new_restQueue = copy.deepcopy(self.restQueue_muster)
        new_restQos_element = copy.deepcopy(self.restQos_muster)
        qos_list_length = len(selfqos_list)
        change = False
  
        for i in range(qos_list_length):
            qos_element = selfqos_list[i]
            if qos_element[REST_MATCH][REST_TP_DST] == port:
               j = i + 1              
               queues[j] = queues.pop(-1)
               new_restQueue[REST_QUEUES] = queues
               selfqueues_single = queues                
               change = True
        
        if change == False:    
           new_restQueue[REST_QUEUES] = queues
           selfqueues_single = queues        
           new_restQos_element[REST_MATCH][REST_TP_DST] = port
           new_restQos_element[REST_ACTION][REST_ACTION_QUEUE] = new_key
	   new_restQos_element[REST_QUEUE_PRIORITY] = priority
           selfqos_list.append(new_restQos_element)
        
        print "22222222" , queues , "------" , selfqos_list

       	
	for i in range(len(queues)):
		old_dict = {}
		if i == 0:
			old_dict[5001] = queues[0]
		else:
			qos_element = selfqos_list[i - 1]
			old_port = qos_element[REST_MATCH][REST_TP_DST]
			old_dict[old_port] = queues[i]
		original_port_rate.append(old_dict)
	return new_restQueue , queues


    





    def set_queue_forAll(self, rest_setQueue , rest_setQos , vlan_id, waiters):
        global selfovs_bridge
        global selfqos_list
        selfqos_list = copy.deepcopy(rest_setQos)        
        if selfovs_bridge is None:
            msg = {'result': 'failure',
                   'details': 'ovs_bridge is not exists'}
            return REST_COMMAND_RESULT, msg
        
        if rest_setQueue is None:
            msg = {'result': 'failure',
                  'details': 'rest_setQueue is not exists'}
            return REST_COMMAND_RESULT, msg

        if rest_setQos is None:
            msg = {'result': 'failure',
                   'details': 'rest_setQos is not exists'}
            return REST_COMMAND_RESULT, msg

	#self.delete_queue({}, 0)
	
#        for restElement in rest_setQos:
#            selfqos_list.append(restElement)
  
        vif_ports = selfovs_bridge.get_port_name_list()
        length = len(vif_ports)
        self.delete_queue({}, 0)  
	self.delete_qos({"qos_id":"all"},0 ,waiters)


        for i in range(length):
           
            restI = copy.deepcopy(rest_setQueue)
            restI[REST_PORT_NAME] = vif_ports[i]
            self.set_queue(restI , vlan_id)
            j = i + 1
            ipaddr = "{0}{1}".format("10.0.0." ,str(j))                     

            for rest_element in rest_setQos:
                rest_element[REST_MATCH][REST_DST_IP] = ipaddr
                self.set_qos(rest_element , 0 , {})
     
        return "chenggong"


    def develop_advanced_queues(self, queues):
	global selfqos_list
        #global selfqueue_list
        #global selfqueues_single
        #global timer 
	#global last_queues
	#global outside_waiters
	#global change
        #global first_time
        #global last_port_stats
	max_rate = self.restQueue_muster[REST_QUEUE_MAX_RATE]
	parent_max_rate = int(max_rate)
	max_bandwidth = parent_max_rate
	pri_set =set()
	pri_list =[]
	#get all priorty, from big to small sort
	for i in range(len(selfqos_list)):
		qos_element = selfqos_list[i]
		pri_set.add(int(qos_element[REST_QUEUE_PRIORITY]))
	pri_list = list(pri_set)
	pri_list.sort(reverse = True)

	
	
	for i in pri_list:
		#print sum_max_rate
		#print "priority=:",i
		qos_number = []
		min_rate_list = []
		#find all priortiy = i ,de qos_id,
		for j in range(len(selfqos_list)):
			qos_element = selfqos_list[j]
			if int(qos_element[REST_QUEUE_PRIORITY]) == i :
				qos_number.append(j)
		#get all min_rate ,calculate sum, and store queue_number
		#print qos_number
		min_rate_queue_list = []
		for k in qos_number:
			k= k +1
			queue_key_list = queues[k].keys()
			if queue_key_list[-1] == "min_rate":
				min_rate_queue_list.append(k)
				min_rate = int(queues[k][queue_key_list[-1]])
				print min_rate
				min_rate_list.append(min_rate)
		#print min_rate_list
		#print min_rate_queue_list 
		#the number of queue in queues
		#sum > 100000, pingfen, < return 
		if parent_max_rate > 0:
			 #print "sum_max_rate >0"
			 #print sum(min_rate_list)
			 if sum(min_rate_list) > parent_max_rate:
			 	print sum(min_rate_list)
				average_rate = parent_max_rate /len(min_rate_list)
				for m in min_rate_queue_list:
					queues[m]["min_rate"] = str(average_rate)
			 elif sum(min_rate_list) < parent_max_rate - len(min_rate_list)*(max_bandwidth/20):
			  	#length = len(min_rate_list)
				#for i in range(len(min_rate_list)):
				i = 0
				for m in min_rate_queue_list:
					min_rate = int(queues[m]["min_rate"])
			 		min_rate = min_rate + (max_bandwidth/20)
					print "i",i,"m",m, min_rate
			 		queues[m]["min_rate"] = str(min_rate)
					min_rate_list[i] = min_rate
					i = i + 1
			 else:
			 	pass
				#print "sum_max_rate:"
			 #print  "before:",sum_max_rate
			 #print "min_rate_list:",min_rate_list
			 parent_max_rate = parent_max_rate -sum(min_rate_list)
			 #print "after:",sum_max_rate
		else:
			for m in min_rate_queue_list:
				queues[m]["min_rate"]= "0"
	return queues



    def request_flow_stats(self):
        
        global timer
        global first_time
        reply = self.port_stats_stop()
#        timer.cancel() 
        if first_time == False:
           first_time = True
           timer = threading.Timer(30 , self.request_flow_stats)   
           timer.start()        
        else:        
#           reply = self.port_stats_stop()
           port1 = selfqos_list[0]
           length = len(reply)
           if length <= 0:
#              if len(selfqos_list) > 1:
#                 self.delete_last_queue(reply)
#                  pass
#              else:
              pass
           elif length <= 1 and length >0:
              if port1[REST_MATCH][REST_TP_DST] in reply:
                  pass             
              else:
                   self.delete_last_queue(reply)
           else:
              self.delete_last_queue(reply)                   
#           timer.cancel() 
           timer = threading.Timer(30 , self.request_flow_stats)      
           timer.start()
        
#        self.delete_last_queue(reply) 

        return 

    
        
    def get_port_stats(self):
        global outside_waiters
        global selfqos_list
        
    
        packet_num = []
        port_list = []
        
      
       
#        flow_port_list = []
        msgs = self.ofctl.get_flow_stats(self.dp, outside_waiters)
        if str(self.dp.id) in msgs:
           flow_stats = msgs[str(self.dp.id)]
           for qos in selfqos_list:
               flow_port_list = []
               port_num = qos[REST_MATCH][REST_TP_DST]

               
               
               for flow_stat in flow_stats:
                   p = flow_stat["match"]
                   pp = p.get("tp_dst")
               
                   if str(pp) == port_num:
                      flow_port_list.append(flow_stat)
               port_list.append(flow_port_list)
        
        port_list_length = len(port_list)
        for i in range(port_list_length):
            port_packet = []
            for port_dst in port_list[i]:
                port_packet.append(port_dst["packet_count"])
            packet_num.append(port_packet)
        
        return packet_num        
                   
    def port_stats_stop(self):
        global last_port_stats
        new_port_stats = self.get_port_stats()
        new_port_stats_length = 0
        reply = []
        if len(new_port_stats) <= len(last_port_stats):
           new_port_stats_length = len(new_port_stats)
        else: 
           new_port_stats_length = len(last_port_stats)
              
        count_list = []
        ll = []
        for i in range(new_port_stats_length):
            port_dst_length = len(new_port_stats[i])
            count = 0
            for j in range(port_dst_length):
                last = last_port_stats[i][j]
#                last = []
                 
                new = new_port_stats[i][j]
                if last == new:
                   count += 1
            count_list.append(count)
            ll.append(port_dst_length)
            if count == port_dst_length:
               qoslist = selfqos_list[i]
               reply.append(qoslist[REST_MATCH][REST_TP_DST])
        last_port_stats = copy.deepcopy(new_port_stats)
        return reply





             
     def delete_last_queue(self,reply):
        global selfqueue_list
        global selfqos_list
        #global timer
        #global selfqueues_single
        #global last_queues
	#global outside_waiters
 	#global change

	global original_port_rate


	current_queues = []
	port_list = []
	port = []
	for i in range(len(original_port_rate)):
		port = original_port_rate[i].keys()
		port_list.append(port[0])


	for i in range(len(port_list)):
		print "daxunhuan",port_list[i]
		if port_list[i] in reply:
			pass
		else:
			print "buzai",i
			port_rate = original_port_rate[i]
			rate = port_rate[port_list[i]]
			current_queues.append(rate)
			#pass			
	#list_number = []
	qos_list = []
	length = len(reply)
	for i in range(length):
		for j in range(len(selfqos_list)):
			qos_element = selfqos_list[j]
			if reply[i] == qos_element[REST_MATCH][REST_TP_DST]:
				qos_list.append(qos_element) 
	
	for i in qos_list:
		selfqos_list.remove(i)
	
	

	current_new_queues = copy.deepcopy(current_queues)	
	advanced_queues = develop_new_queues(current_new_queues)

	new_restQueue = copy.deepcopy(self.restQueue_muster)
	new_restQueue[REST_QUEUES] = copy.deepcopy(advanced_queues)

	self.set_queue_forAll(new_restQueue , selfqos_list , 0, outside_waiters)
        
	return  "shanchule"
	

       


    #def delete_last_queue(self , reply):
     #   global selfqueue_list
      #  global selfqos_list
       # global timer
#        global selfqueues_single
       # global last_queues
#	global outside_waiters
 #	global change

#	if change == False:
 #       	selfqos_list.pop(-1)
#                selfqueues_single.pop(-1)
  #      new_restQueue = copy.deepcopy(self.restQueue_muster)
   #     new_restQueue[REST_QUEUES] = copy.deepcopy(last_queues)
#        timer.cancel() 

    #    self.set_queue_forAll(new_restQueue , selfqos_list , 0, outside_waiters)
#        timer.cancel()
     #   return  "shuijiaolekeyi" 


    def _delete_queue(self):
        global selfovs_bridgei
        if selfovs_bridge is None:
            return False

        vif_ports = selfovs_bridge.get_external_ports()
        for port in vif_ports:
            selfovs_bridge.del_qos(port.port_name)
        return True

    @rest_command
    def delete_queue(self, rest, vlan_id):
        if self._delete_queue():
            msg = 'success'
            selfqueue_list.clear()
        else:
            msg = 'failure'

        return REST_COMMAND_RESULT, msg

    @rest_command
    def set_qos(self, rest, vlan_id, waiters):
        msgs = []
        cookie_list = self._get_cookie(vlan_id)
        for cookie, vid in cookie_list:
            msg = self._set_qos(cookie, rest, waiters, vid)
            msgs.append(msg)
        return REST_COMMAND_RESULT, msgs

    def _set_qos(self, cookie, rest, waiters, vlan_id):
        match_value = rest[REST_MATCH]
        if vlan_id:
            match_value[REST_DL_VLAN] = vlan_id

        priority = int(rest.get(REST_PRIORITY, QOS_PRIORITY_MIN))
        if (QOS_PRIORITY_MAX < priority):
            raise ValueError('Invalid priority value. Set [%d-%d]'
                             % (QOS_PRIORITY_MIN, QOS_PRIORITY_MAX))

        match = Match.to_openflow(match_value)

        actions = []
        action = rest.get(REST_ACTION, None)
        if action is not None:
            if REST_ACTION_MARK in action:
                actions.append({'type': 'SET_FIELD',
                                'field': REST_DSCP,
                                'value': int(action[REST_ACTION_MARK])})
            if REST_ACTION_METER in action:
                actions.append({'type': 'METER',
                                'meter_id': action[REST_ACTION_METER]})
            if REST_ACTION_QUEUE in action:
                actions.append({'type': 'SET_QUEUE',
                                'queue_id': action[REST_ACTION_QUEUE]})
        else:
            actions.append({'type': 'SET_QUEUE',
                            'queue_id': 0})

        actions.append({'type': 'GOTO_TABLE',
                        'table_id': QOS_TABLE_ID + 1})
        flow = self._to_of_flow(cookie=cookie, priority=priority,
                                match=match, actions=actions)

        cmd = self.dp.ofproto.OFPFC_ADD
        try:
            self.ofctl.mod_flow_entry(self.dp, flow, cmd)
        except:
            raise ValueError('Invalid rule parameter.')

        qos_id = QoS._cookie_to_qosid(cookie)
        msg = {'result': 'success',
               'details': 'QoS added. : qos_id=%d' % qos_id}

        if vlan_id != VLANID_NONE:
            msg.setdefault(REST_VLANID, vlan_id)
        return msg

    @rest_command
    def get_qos(self, rest, vlan_id, waiters):
        rules = {}
        msgs = self.ofctl.get_flow_stats(self.dp, waiters)
        if str(self.dp.id) in msgs:
            flow_stats = msgs[str(self.dp.id)]
            for flow_stat in flow_stats:
                if flow_stat['table_id'] != QOS_TABLE_ID:
                    continue
                priority = flow_stat[REST_PRIORITY]
                if priority != DEFAULT_FLOW_PRIORITY:
                    vid = flow_stat[REST_MATCH].get(REST_DL_VLAN, VLANID_NONE)
                    if vlan_id == REST_ALL or vlan_id == vid:
                        rule = self._to_rest_rule(flow_stat)
                        rules.setdefault(vid, [])
                        rules[vid].append(rule)

        get_data = []
        for vid, rule in rules.items():
            if vid == VLANID_NONE:
                vid_data = {REST_QOS: rule}
            else:
                vid_data = {REST_VLANID: vid, REST_QOS: rule}
            get_data.append(vid_data)  
        return REST_COMMAND_RESULT, get_data

    @rest_command
    def delete_qos(self, rest, vlan_id, waiters):
        try:
            if rest[REST_QOS_ID] == REST_ALL:
                qos_id = REST_ALL
            else:
                qos_id = int(rest[REST_QOS_ID])
        except:
            raise ValueError('Invalid qos id.')

        vlan_list = []
        delete_list = []

        msgs = self.ofctl.get_flow_stats(self.dp, waiters)
        if str(self.dp.id) in msgs:
            flow_stats = msgs[str(self.dp.id)]
            for flow_stat in flow_stats:
                cookie = flow_stat[REST_COOKIE]
                ruleid = QoS._cookie_to_qosid(cookie)
                priority = flow_stat[REST_PRIORITY]
                dl_vlan = flow_stat[REST_MATCH].get(REST_DL_VLAN, VLANID_NONE)

                if priority != DEFAULT_FLOW_PRIORITY:
                    if ((qos_id == REST_ALL or qos_id == ruleid) and
                            (vlan_id == dl_vlan or vlan_id == REST_ALL)):
                        match = Match.to_mod_openflow(flow_stat[REST_MATCH])
                        delete_list.append([cookie, priority, match])
                    else:
                        if dl_vlan not in vlan_list:
                            vlan_list.append(dl_vlan)

        self._update_vlan_list(vlan_list)

        if len(delete_list) == 0:
            msg_details = 'QoS rule is not exist.'
            if qos_id != REST_ALL:
                msg_details += ' : QoS ID=%d' % qos_id
            msg = {'result': 'failure',
                   'details': msg_details}
        else:
            cmd = self.dp.ofproto.OFPFC_DELETE_STRICT
            actions = []
            delete_ids = {}
            for cookie, priority, match in delete_list:
                flow = self._to_of_flow(cookie=cookie, priority=priority,
                                        match=match, actions=actions)
                self.ofctl.mod_flow_entry(self.dp, flow, cmd)

                vid = match.get(REST_DL_VLAN, VLANID_NONE)
                rule_id = QoS._cookie_to_qosid(cookie)
                delete_ids.setdefault(vid, '')
                delete_ids[vid] += (('%d' if delete_ids[vid] == ''
                                     else ',%d') % rule_id)

            msg = []
            for vid, rule_ids in delete_ids.items():
                del_msg = {'result': 'success',
                           'details': ' deleted. : QoS ID=%s' % rule_ids}
                if vid != VLANID_NONE:
                    del_msg.setdefault(REST_VLANID, vid)
                msg.append(del_msg)

        return REST_COMMAND_RESULT, msg

    @rest_command
    def set_meter(self, rest, vlan_id, waiters):
        if self.version == ofproto_v1_0.OFP_VERSION:
            raise ValueError('set_meter operation is not supported')

        msgs = []
        msg = self._set_meter(rest, waiters)
        msgs.append(msg)
        return REST_COMMAND_RESULT, msgs

    def _set_meter(self, rest, waiters):
        cmd = self.dp.ofproto.OFPMC_ADD
        try:
            self.ofctl.mod_meter_entry(self.dp, rest, cmd)
        except:
            raise ValueError('Invalid meter parameter.')

        msg = {'result': 'success',
               'details': 'Meter added. : Meter ID=%s' %
               rest[REST_METER_ID]}
        return msg

    @rest_command
    def get_meter(self, rest, vlan_id, waiters):
        if (self.version == ofproto_v1_0.OFP_VERSION or
                self.version == ofproto_v1_2.OFP_VERSION):
            raise ValueError('get_meter operation is not supported')

        msgs = self.ofctl.get_meter_stats(self.dp, waiters)
        return REST_COMMAND_RESULT, msgs

    @rest_command
    def delete_meter(self, rest, vlan_id, waiters):
        if (self.version == ofproto_v1_0.OFP_VERSION or
                self.version == ofproto_v1_2.OFP_VERSION):
            raise ValueError('delete_meter operation is not supported')

        cmd = self.dp.ofproto.OFPMC_DELETE
        try:
            self.ofctl.mod_meter_entry(self.dp, rest, cmd)
        except:
            raise ValueError('Invalid meter parameter.')

        msg = {'result': 'success',
               'details': 'Meter deleted. : Meter ID=%s' %
               rest[REST_METER_ID]}
        return REST_COMMAND_RESULT, msg

    def _to_of_flow(self, cookie, priority, match, actions):
        flow = {'cookie': cookie,
                'priority': priority,
                'flags': 0,
                'idle_timeout': 0,
                'hard_timeout': 0,
                'match': match,
                'actions': actions}
        return flow

    def _to_rest_rule(self, flow):
        ruleid = QoS._cookie_to_qosid(flow[REST_COOKIE])
        rule = {REST_QOS_ID: ruleid}
        rule.update({REST_PRIORITY: flow[REST_PRIORITY]})
        rule.update(Match.to_rest(flow))
        rule.update(Action.to_rest(flow))
        return rule


class Match(object):

    _CONVERT = {REST_DL_TYPE:
                {REST_DL_TYPE_ARP: ether.ETH_TYPE_ARP,
                 REST_DL_TYPE_IPV4: ether.ETH_TYPE_IP,
                 REST_DL_TYPE_IPV6: ether.ETH_TYPE_IPV6},
                REST_NW_PROTO:
                {REST_NW_PROTO_TCP: inet.IPPROTO_TCP,
                 REST_NW_PROTO_UDP: inet.IPPROTO_UDP,
                 REST_NW_PROTO_ICMP: inet.IPPROTO_ICMP,
                 REST_NW_PROTO_ICMPV6: inet.IPPROTO_ICMPV6}}

    @staticmethod
    def to_openflow(rest):

        def __inv_combi(msg):
            raise ValueError('Invalid combination: [%s]' % msg)

        def __inv_2and1(*args):
            __inv_combi('%s=%s and %s' % (args[0], args[1], args[2]))

        def __inv_2and2(*args):
            __inv_combi('%s=%s and %s=%s' % (
                args[0], args[1], args[2], args[3]))

        def __inv_1and1(*args):
            __inv_combi('%s and %s' % (args[0], args[1]))

        def __inv_1and2(*args):
            __inv_combi('%s and %s=%s' % (args[0], args[1], args[2]))

        match = {}

        # error check
        dl_type = rest.get(REST_DL_TYPE)
        nw_proto = rest.get(REST_NW_PROTO)
        if dl_type is not None:
            if dl_type == REST_DL_TYPE_ARP:
                if REST_SRC_IPV6 in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_ARP, REST_SRC_IPV6)
                if REST_DST_IPV6 in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_ARP, REST_DST_IPV6)
                if REST_DSCP in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_ARP, REST_DSCP)
                if nw_proto:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_ARP, REST_NW_PROTO)
            elif dl_type == REST_DL_TYPE_IPV4:
                if REST_SRC_IPV6 in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_IPV4, REST_SRC_IPV6)
                if REST_DST_IPV6 in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_IPV4, REST_DST_IPV6)
                if nw_proto == REST_NW_PROTO_ICMPV6:
                    __inv_2and2(
                        REST_DL_TYPE, REST_DL_TYPE_IPV4,
                        REST_NW_PROTO, REST_NW_PROTO_ICMPV6)
            elif dl_type == REST_DL_TYPE_IPV6:
                if REST_SRC_IP in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_IPV6, REST_SRC_IP)
                if REST_DST_IP in rest:
                    __inv_2and1(
                        REST_DL_TYPE, REST_DL_TYPE_IPV6, REST_DST_IP)
                if nw_proto == REST_NW_PROTO_ICMP:
                    __inv_2and2(
                        REST_DL_TYPE, REST_DL_TYPE_IPV6,
                        REST_NW_PROTO, REST_NW_PROTO_ICMP)
            else:
                raise ValueError('Unknown dl_type : %s' % dl_type)
        else:
            if REST_SRC_IP in rest:
                if REST_SRC_IPV6 in rest:
                    __inv_1and1(REST_SRC_IP, REST_SRC_IPV6)
                if REST_DST_IPV6 in rest:
                    __inv_1and1(REST_SRC_IP, REST_DST_IPV6)
                if nw_proto == REST_NW_PROTO_ICMPV6:
                    __inv_1and2(
                        REST_SRC_IP, REST_NW_PROTO, REST_NW_PROTO_ICMPV6)
                rest[REST_DL_TYPE] = REST_DL_TYPE_IPV4
            elif REST_DST_IP in rest:
                if REST_SRC_IPV6 in rest:
                    __inv_1and1(REST_DST_IP, REST_SRC_IPV6)
                if REST_DST_IPV6 in rest:
                    __inv_1and1(REST_DST_IP, REST_DST_IPV6)
                if nw_proto == REST_NW_PROTO_ICMPV6:
                    __inv_1and2(
                        REST_DST_IP, REST_NW_PROTO, REST_NW_PROTO_ICMPV6)
                rest[REST_DL_TYPE] = REST_DL_TYPE_IPV4
            elif REST_SRC_IPV6 in rest:
                if nw_proto == REST_NW_PROTO_ICMP:
                    __inv_1and2(
                        REST_SRC_IPV6, REST_NW_PROTO, REST_NW_PROTO_ICMP)
                rest[REST_DL_TYPE] = REST_DL_TYPE_IPV6
            elif REST_DST_IPV6 in rest:
                if nw_proto == REST_NW_PROTO_ICMP:
                    __inv_1and2(
                        REST_DST_IPV6, REST_NW_PROTO, REST_NW_PROTO_ICMP)
                rest[REST_DL_TYPE] = REST_DL_TYPE_IPV6
            elif REST_DSCP in rest:
                # Apply dl_type ipv4, if doesn't specify dl_type
                rest[REST_DL_TYPE] = REST_DL_TYPE_IPV4
            else:
                if nw_proto == REST_NW_PROTO_ICMP:
                    rest[REST_DL_TYPE] = REST_DL_TYPE_IPV4
                elif nw_proto == REST_NW_PROTO_ICMPV6:
                    rest[REST_DL_TYPE] = REST_DL_TYPE_IPV6
                elif nw_proto == REST_NW_PROTO_TCP or \
                        nw_proto == REST_NW_PROTO_UDP:
                    raise ValueError('no dl_type was specified')
                else:
                    raise ValueError('Unknown nw_proto: %s' % nw_proto)

        for key, value in rest.items():
            if key in Match._CONVERT:
                if value in Match._CONVERT[key]:
                    match.setdefault(key, Match._CONVERT[key][value])
                else:
                    raise ValueError('Invalid rule parameter. : key=%s' % key)
            else:
                match.setdefault(key, value)

        return match

    @staticmethod
    def to_rest(openflow):
        of_match = openflow[REST_MATCH]

        mac_dontcare = mac.haddr_to_str(mac.DONTCARE)
        ip_dontcare = '0.0.0.0'
        ipv6_dontcare = '::'

        match = {}
        for key, value in of_match.items():
            if key == REST_SRC_MAC or key == REST_DST_MAC:
                if value == mac_dontcare:
                    continue
            elif key == REST_SRC_IP or key == REST_DST_IP:
                if value == ip_dontcare:
                    continue
            elif key == REST_SRC_IPV6 or key == REST_DST_IPV6:
                if value == ipv6_dontcare:
                    continue
            elif value == 0:
                continue

            if key in Match._CONVERT:
                conv = Match._CONVERT[key]
                conv = dict((value, key) for key, value in conv.items())
                match.setdefault(key, conv[value])
            else:
                match.setdefault(key, value)

        return match

    @staticmethod
    def to_mod_openflow(of_match):
        mac_dontcare = mac.haddr_to_str(mac.DONTCARE)
        ip_dontcare = '0.0.0.0'
        ipv6_dontcare = '::'

        match = {}
        for key, value in of_match.items():
            if key == REST_SRC_MAC or key == REST_DST_MAC:
                if value == mac_dontcare:
                    continue
            elif key == REST_SRC_IP or key == REST_DST_IP:
                if value == ip_dontcare:
                    continue
            elif key == REST_SRC_IPV6 or key == REST_DST_IPV6:
                if value == ipv6_dontcare:
                    continue
            elif value == 0:
                continue

            match.setdefault(key, value)

        return match


class Action(object):

    @staticmethod
    def to_rest(flow):
        if REST_ACTION in flow:
            actions = []
            for act in flow[REST_ACTION]:
                field_value = re.search(r'SET_FIELD: \{ip_dscp:(\d+)', act)
                if field_value:
                    actions.append({REST_ACTION_MARK: field_value.group(1)})
                meter_value = re.search(r'METER:(\d+)', act)
                if meter_value:
                    actions.append({REST_ACTION_METER: meter_value.group(1)})
                queue_value = re.search(r'SET_QUEUE:(\d+)', act)
                if queue_value:
                    actions.append({REST_ACTION_QUEUE: queue_value.group(1)})
            action = {REST_ACTION: actions}
        else:
            action = {REST_ACTION: 'Unknown action type.'}

        return action
