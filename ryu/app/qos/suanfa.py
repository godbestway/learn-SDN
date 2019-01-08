REST_QUEUE_PRIORITY = 'queue_priortity'
REST_DST_IP ='nw_dst'


import copy
REST_QUEUE_MAX_RATE = 'max_rate'
REST_QUEUE_MIN_RATE = 'min_rate'
REST_NW_PROTO_UDP = 'UDP'
REST_TP_DST ='tp_dst'
REST_ACTION = 'actions'
REST_ACTION_QUEUE ='queue'
REST_MATCH ='match'
REST_NW_PROTO ='nw_proto'
REST_QUEUE_TYPE = 'type'
REST_PORT_NAME = 'port_name'
REST_DST_IP = 'nw_dst'
REST_QUEUES = 'queues'
rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5002"}
rest_action = {REST_ACTION_QUEUE:"1"}
rest1 = {REST_QUEUE_PRIORITY : "0",REST_MATCH:rest_match, REST_ACTION:rest_action}

rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5003"}
rest_action = {REST_ACTION_QUEUE:"2"}
rest2 = {REST_QUEUE_PRIORITY : "0",REST_MATCH:rest_match , REST_ACTION:rest_action}

rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5004"}
rest_action = {REST_ACTION_QUEUE:"3"}
rest3 = {REST_QUEUE_PRIORITY : "1",REST_MATCH:rest_match , REST_ACTION:rest_action}

rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5005"}
rest_action = {REST_ACTION_QUEUE:"4"}
rest4 = {REST_QUEUE_PRIORITY : "1",REST_MATCH:rest_match , REST_ACTION:rest_action}

rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5006"}
rest_action = {REST_ACTION_QUEUE:"5"}
rest5 = {REST_QUEUE_PRIORITY : "2",REST_MATCH:rest_match , REST_ACTION:rest_action}

rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:"5007"}
rest_action = {REST_ACTION_QUEUE:"6"}
rest6 = {REST_QUEUE_PRIORITY : "2",REST_MATCH:rest_match , REST_ACTION:rest_action}
selfqos_list = []
selfqos_list.append(rest1)
#selfqos_list.append(rest2)
#selfqos_list.append(rest3)
#selfqos_list.append(rest4)
#selfqos_list.append(rest5)
#selfqos_list.append(rest6)
restQueue_muster = {REST_PORT_NAME:"" , REST_QUEUE_TYPE:"linux-htb" , REST_QUEUE_MAX_RATE:"1000000" , REST_QUEUES:[]}
rest_match = {REST_DST_IP:"" , REST_NW_PROTO:"UDP" , REST_TP_DST:""}
rest_action = {REST_ACTION_QUEUE:""}
restQos_muster = {REST_QUEUE_PRIORITY:"0", REST_MATCH:rest_match , REST_ACTION:rest_action}

#reply = ["5004","5007"]
queues = [{"max_rate": "800000"},{"min_rate": "600000"}]
#queues=[{"max_rate": "800000"}, {"min_rate": "600000"},{"min_rate": "400000"},{"min_rate": "500000"},{"min_rate": "600000"},{"max_rate": "700000"},{"min_rate": "800000"}]
#queues=[{"max_rate": "800000"}, {"min_rate": "600000"},{"min_rate": "500000"},{"min_rate": "400000"},{"min_rate": "300000"},{"min_rate": "200000"},{"min_rate": "100000"}]
#queues=[{"max_rate": "800000"}, {"min_rate": "600000"},{"min_rate": "400000"},{"min_rate": "500000"},{"min_rate": "600000"},{"min_rate": "700000"},{"min_rate": "800000"}] 
sum_max_rate = 1000000
#left_max_rate = 0
def develop_new_queues(queues):
	global sum_max_rate
	max_bandwidth = sum_max_rate
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
		if sum_max_rate > 0:
			 #print "sum_max_rate >0"
			 #print sum(min_rate_list)
			 if sum(min_rate_list) > sum_max_rate:
			 	print sum(min_rate_list)
				average_rate = sum_max_rate /len(min_rate_list)
				for m in min_rate_queue_list:
					queues[m]["min_rate"] = str(average_rate)
			 elif sum(min_rate_list) < sum_max_rate - len(min_rate_list)*(max_bandwidth/20):
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
			 sum_max_rate = sum_max_rate -sum(min_rate_list)
			 #print "after:",sum_max_rate
		else:
			for m in min_rate_queue_list:
				queues[m]["min_rate"]= "0"
	return queues			
				
				

"""if sum(min_rate_list) >= sum_max_rate:
 82                                 print "sum_min_rate>0"
  83                                 average_rate = sum_max_rate/len(min_rate_list)
   84                                 for m in min_rate_queue_list:
    85                                         queues[m]["min_rate"]= str(average_rate)                          
     86                                 break   
      87 
       88                         else:
        89                                 print "sum_min_rate < 0"
	 90                                 sum_max_rate = sum_max_rate - sum(min_rate_list)
	  91                                 continue"""


"""


"""


#print develop_new_queues(queues)
#print rest1[REST_QUEUE_PRIORITY]
#pri_list = set()
#pri_list.add(1)
#pri_list.add(1)
#pri_list.add(2)
#tuple_pri_list = tuple(pri_list)
#print tuple_pri_list


original_port_rate = []
for i in range(len(queues)):
		old_dict = {}
		rate = {}
		rate = queues[i]
		if i == 0:
			old_dict[5001] = rate
		else:
			#rate = {}
			#rate = queues[i]
			i = i-1
			qos_element = selfqos_list[i]
			old_port = qos_element[REST_MATCH][REST_TP_DST]
			old_dict[old_port] = rate
		original_port_rate.append(old_dict)

#print original_port_rate
#print dict(original_port_rate)

def delete_last_queue(reply):
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
			print "\n"
			print "rate",rate
			current_queues.append(rate)
			#pass			
	#list_number = []
	print current_queues
	qos_list = []
	length = len(reply)
	for i in range(length):
		for j in range(len(selfqos_list)):
			qos_element = selfqos_list[j]
			if reply[i] == qos_element[REST_MATCH][REST_TP_DST]:
				qos_list.append(qos_element) 
			#else:print "\n"
				#qos_element[REST_ACTION][REST_ACTION_QUEUE] = str(m)
				#m = m +1
	for i in qos_list:
	 	selfqos_list.remove(i)
	
	for i in range(len(current_queues)-1):
		qos_element = selfqos_list[i]
		qos_element[REST_ACTION][REST_ACTION_QUEUE] = str(i+1)
		#print "\n"
		#print i
	
	#for i in qos_list:
		#selfqos_list.remove(i)

	new_queues = copy.deepcopy(current_queues)
	advanced_queues = develop_new_queues(new_queues)			
        return  selfqos_list, current_queues, advanced_queues


#print delete_last_queue(reply)






#global original_port_rate

original_port_rate = [] 
original_port_rate.append({"5001":{REST_QUEUE_MAX_RATE:"800000"}})
original_port_rate.append({"5002":{REST_QUEUE_MIN_RATE:"600000"}})

def develop_regular_queues(port , priority , come_min_rate, come_max_rate):
    	global selfqos_list
	global change
        global original_port_rate
	queues = []
#	original_port_rate = []
        put_rate = {}

        all_keys = []
        k = original_port_rate[0].keys()
        k0 = k[0]
        #all_keys.append(k0)
        queues.append(original_port_rate[0][k0])
        for port_queue in original_port_rate:
            keys = port_queue.keys()
            key = keys[0]
            all_keys.append(key)
            for qos in selfqos_list:
                
                if qos[REST_MATCH][REST_TP_DST] == key:
                   queues.append(port_queue[key])

	print all_keys
	print "before",queues
		
	if come_min_rate != None:
		queues.append({REST_QUEUE_MIN_RATE:come_min_rate})
                put_rate = {REST_QUEUE_MIN_RATE:come_min_rate}
	else:
		queues.append({REST_QUEUE_MAX_RATE:come_max_rate})
                put_rate = {REST_QUEUE_MIN_RATE:come_min_rate}            

        new_restQueue = copy.deepcopy(restQueue_muster)
        new_restQos_element = copy.deepcopy(restQos_muster)
#        queue_list_length = len(original_port_rate)
        change = False
        qos_list_length = len(selfqos_list)
	print "after",queues
	print change
#        keys = original_port_rate.keys()
        for i in range(qos_list_length):
		print i	
#            qos_element = original_port_rate[i]
        	#print selfqos_list[i][REST_MATCH][REST_TP_DST]
        	if selfqos_list[i][REST_MATCH][REST_TP_DST] == port:
               		#print "selfqos_list[i][REST_MATCH][REST_TP_DST]"
	       		j = i + 1              
               		#queues[j] = queues[-1]
               		queues[j] = queues.pop(-1)
                	p =all_keys.index(port)
#               queues[i] = put_rate
	       		print "j",j
			print "--------------\n"
			print "p",p
			print"-----------------\n"
	       		print "port",port
			print"--------------\n"
               		original_port_rate[p][port] = put_rate
               		new_restQueue[REST_QUEUES] = queues
#               selfqueues_single = queues                
               		change = True
        
        if change == False:
#           for i in range(queue_list_length):    
           new_restQueue[REST_QUEUES] = queues
#           selfqueues_single = queues        
           new_restQos_element[REST_MATCH][REST_TP_DST] = port
           new_restQos_element[REST_ACTION][REST_ACTION_QUEUE] = str(len(selfqos_list) + 1)
	   new_restQos_element[REST_QUEUE_PRIORITY] = priority
           selfqos_list.append(new_restQos_element)
           original_port_rate.append({port:put_rate})


	print "original:",original_port_rate,"\n"   
	return "queues:",queues,"\n" ,"selfqos_list:",selfqos_list

print develop_regular_queues("5002" ," 0 ", "800000", None)
print "-----------------------------\n"
print develop_regular_queues("5003" ," 1 ", "500000", None)


        #last_port_stats

