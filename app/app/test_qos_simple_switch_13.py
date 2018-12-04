# Copyright (C)
#2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

from ryu import cfg
from ryu.app import rest_qoos
from rest_qos import QoS

from rest_qoos import REST_PORT_NAME 
from rest_qoos import REST_QUEUE_TYPE
from rest_qoos import REST_QUEUE_MAX_RATE 
from rest_qoos import REST_QUEUE_MIN_RATE 
from rest_qoos import REST_QUEUES 
from rest_qoos import REST_MATCH
from rest_qoos import REST_SRC_IP
from rest_qoos import REST_DST_IP
from rest_qoos import REST_NW_PROTO
from rest_qoos import REST_NW_PROTO_TCP
from rest_qoos import REST_NW_PROTO_UDP
from rest_qoos import REST_ACTION
from rest_qoos import REST_TP_DST
from rest_qoos import REST_ACTION_QUEUE

from rest_qos import Match
from rest_qos import Action

class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, table_id=1)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst, table_id=1)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch





        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        

        ovsdb_addr = "tcp:127.0.0.1:6632"
        
        CONF = cfg.CONF
        #self.logger.info(CONF)
        dp = datapath
        qos = QoS(dp , CONF)
        #self.logger.info(qos)
        dp_id = datapath.id
        #self.logger.info("datapathdezhi")
        #self.logger.info(datapath)
        #self.logger.info("dpiddezhi")
        #self.logger.info(dp_id)
        
        
        qos.set_ovsdb_addr(dp_id , ovsdb_addr)
        self.logger.info("yijingyunxingwansetovsdb")
        self.logger.info(qos.ovsdb_addr)
        self.logger.info(qos.ovs_bridge)
        

        queues = []
        queues.append({REST_QUEUE_MAX_RATE:"800000"})
	queues.append({REST_QUEUE_MIN_RATE:"500000"})
        #queues[2] = {REST_QUEUES_MIN_RATE:"500000"}
        rest1 = {REST_PORT_NAME:"s1-eth1" , REST_QUEUE_TYPE:"linux-htb" , REST_QUEUE_MAX_RATE:"1000000" , REST_QUEUES:queues}
        vlan_id=2
        qos.set_queue(rest1,vlan_id)
        self.logger.info(qos.get_queue(rest1, vlan_id))

        match_choice={REST_DST_IP: "10.0.0.1",REST_NW_PROTO: "UDP", REST_TP_DST: "5002"}
	action_choice={REST_ACTION_QUEUE:1}
        rest2={REST_MATCH:match_choice, REST_ACTION: action_choice}
	match=Match()
	self.logger.info(match.to_openflow(match_choice))
	
	waiters=None
	#qos.set_qos(rest2, vlan_id, waiters)
        self.logger.info(qos.set_qos(rest2,vlan_id, waiters))      


        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet 
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)
