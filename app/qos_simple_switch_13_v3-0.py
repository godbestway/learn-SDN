# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
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

from rest_qoos import REST_ACTION 
from rest_qoos import REST_PORT_NAME
from rest_qoos import REST_QUEUE_TYPE
from rest_qoos import REST_QUEUE_MAX_RATE
from rest_qoos import REST_QUEUE_MIN_RATE
from rest_qoos import REST_QUEUES  
from rest_qoos import REST_MATCH 
from rest_qoos import REST_IN_PORT 
from rest_qoos import REST_SRC_MAC 
from rest_qoos import REST_DST_MAC 
from rest_qoos import REST_DL_TYPE 
from rest_qoos import REST_DL_TYPE_ARP 
from rest_qoos import REST_DL_TYPE_IPV4
from rest_qoos import REST_DL_TYPE_IPV6
from rest_qoos import REST_DL_VLAN 
from rest_qoos import REST_SRC_IP
from rest_qoos import REST_DST_IP
from rest_qoos import REST_SRC_IPV6
from rest_qoos import REST_DST_IPV6
from rest_qoos import REST_NW_PROTO 
from rest_qoos import REST_NW_PROTO_TCP 
from rest_qoos import REST_NW_PROTO_UDP 
from rest_qoos import REST_NW_PROTO_ICMP 
from rest_qoos import REST_NW_PROTO_ICMPV6
from rest_qoos import REST_TP_SRC 
from rest_qoos import REST_TP_DST 
from rest_qoos import REST_DSCP 
from rest_qoos import REST_ACTION
from rest_qoos import REST_ACTION_QUEUE
from rest_qoos import REST_ACTION_MARK 
from rest_qoos import REST_ACTION_METER 


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        self.logger.info("switchfeaturehahahahhahahahah")
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser


        #set ovsdb address        
        ovsdb_addr = "tcp:127.0.0.1:6632"
        CONF = cfg.CONF
        dp = datapath
        qos = QoS(dp , CONF)
        dp_id = datapath.id
        qos.set_ovsdb_addr(dp_id , ovsdb_addr)
        
        self.add_Switch_Port(qos , "s1-eth1" , "10.0.0.1")
        self.add_Switch_Port(qos , "s1-eth2" , "10.0.0.2")
        self.add_Switch_Port(qos , "s1-eth3" , "10.0.0.3")


 
        
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


    def add_Switch_Port(self , qos , port_name , ip_addr):
        sqos = qos
        #set queues
        queues = []
        queues.append({REST_QUEUE_MAX_RATE:"800000"})
        queues.append({REST_QUEUE_MIN_RATE:"100000"})
        queues.append({REST_QUEUE_MIN_RATE:"900000"})
        self.logger.info("packetinhahahahahhahaha")
        rest = {REST_PORT_NAME:port_name , REST_QUEUE_TYPE:"linux-htb" , REST_QUEUE_MAX_RATE:"1000000" , REST_QUEUES:queues}
        self.logger.info(sqos.set_queue(rest , 0))

        #set qos rules
        rest_match = {REST_DST_IP:ip_addr , REST_NW_PROTO:"UDP" , REST_TP_DST:"5002" , REST_DSCP:"26"}
        rest_action = {REST_ACTION_QUEUE:"1" , REST_ACTION_MARK:"26" }
        rest2 = {REST_MATCH:rest_match , REST_ACTION:rest_action}
        self.logger.info(sqos.set_qos(rest2 , 0 , None))

        rest_match = {REST_DST_IP:ip_addr , REST_NW_PROTO:"UDP" , REST_TP_DST:"5003" , REST_DSCP:"34"}
        rest_action = {REST_ACTION_QUEUE:"2" , REST_ACTION_MARK:"34" }
        rest2 = {REST_MATCH:rest_match , REST_ACTION:rest_action}
        self.logger.info(sqos.set_qos(rest2 , 0 , None))
        self.logger.info("packetinhehehehehehehehe")

   

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
