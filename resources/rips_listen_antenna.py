#!/usr/bin/python
# coding: utf-8
import os
import sys
import traceback
import socket
from threading import Thread, Lock, Timer
import json
import time
from collections import deque
import logging
from fann2 import libfann


debug = True

FORMAT = '%(asctime)s - %(message)s'
#FORMAT = "%(asctime)s:%(levelname)s:%(message)s"
CAPTURE_FILE = "captureRssi.txt"
MAX_ITEM = 2000
queue = None
#mode = 'Learn'
mode = 'Analyze'
mutex = Lock()
status = "scan"

if debug :
    logLevel=logging.DEBUG
    logLevel=logging.INFO
    logging.basicConfig(format=FORMAT,level=logLevel)
else :
    logLevel=logging.CRITICAL    
    logging.basicConfig(format=FORMAT,level=logLevel)

class Neuron:
    
    def __init__(self):
        self.ann = libfann.neural_net()
        self.ann.create_from_file("training_result")
        self.undetermined_sample = []
        
    def run(self,sample):
        result = self.ann.run(sample)
        logging.debug (result)
        return result
    
    def add_undetermined_sample(self,sample,result):
        global debug
        self.undetermined_sample.append(sample)
        if debug:
            print(result)

ann = Neuron();

class Antennas:
    ANTENNA1 = 'raspberrypi'
    ANTENNA2 = 'Jeedom'
    ANTENNA3 = 'cuisine'
    ANTENNAS = [ANTENNA1,ANTENNA2,ANTENNA3]
      
class Rooms:
    SALON = 'Salon'
    ENTREE = 'Entrée'
    CHAMBRE = 'Chambre'
    UNKNOWN = 'Unknown'
    MISSING = 'Missing'
    LOCATIONS = [SALON,ENTREE,CHAMBRE]
      
class Tags:
    tags_dict = {}
    _maxDelay = 200
    def __init__(self,mac):
        global mutex
        mutex.acquire()
        self.mac = mac
        self.position = Rooms.UNKNOWN
        self.rssiValues = []
        self.historic = []
        self.lastSeen = 0
        self.maxDelay = 0
        Tags.tags_dict[mac]=self
        mutex.release()
    
    def get_mac(self):
        return self.mac
    
    def set_room(self,room):
        global mutex
        mutex.acquire()
        self.position = room
        if room == Rooms.MISSING:
            delay = int(time.time())-self.lastSeen
            if delay > self.maxDelay and delay < Tags._maxDelay/2:
                self.maxDelay = delay
        mutex.release()
    
    def get_room(self):
        return self.position
        
    def add_rssi(self,antenna,timestamp,rssi):
        global mutex
        mutex.acquire()
        self.rssiValues.append([antenna, timestamp,rssi])
        if self.lastSeen != 0:
            delay = int(time.time())-self.lastSeen
            if delay > self.maxDelay and delay < Tags._maxDelay:
                self.maxDelay = delay
            #print ("delay=",delay,self.maxDelay,self.mac)
        self.lastSeen = timestamp
        if self.position == Rooms.MISSING :
            self.position = Rooms.UNKNOWN
        mutex.release()
        
    def remove_rssi(self,antenna,timestamp,rssi):
        global mutex
        mutex.acquire()
        self.rssiValues.remove([antenna, timestamp,rssi])
        mutex.release()
    
    def remove_first_rssi(self):
        global mutex
        mutex.acquire()
        self.rssiValues.pop(0)
        mutex.release()
    
    def list_rssi(self):
        global debug   
        for tab in self.rssiValues :
            if debug:
                print ('value = ',tab)
    
    def get_rssi(self):   
        return self.rssiValues
    
    def first_rssi(self):
        if len(self.rssiValues) > 0 :   
            return self.rssiValues[0]
        else :
            return []
    
    def last_rssi(self):
        if len(self.rssiValues) > 0 :   
            return self.rssiValues[-1]
        else :
            return []
    
    def count_rssi(self):
        return len(self.rssiValues)
    
    def add_historic(self,sample):
        self.historic.append(sample)
        
    def list_historic(self):
        for tab in self.historic :
            print (tab)
            
    def get_last_seen(self):
        return self.lastSeen
    
    def get_max_delay(self):
        return self.maxDelay


class AnalyzeRips:
    __deltat = 5
    _missingRssi = -110
    
    def auto_learn(tag,sample):
        if min(sample) == AnalyzeRips._missingRssi:
            return
        room1 = sample[0]+sample[1]+sample[2]
        room2 = sample[3]+sample[4]+sample[5]
        room3 = sample[6]+sample[7]+sample[8]
        room = max([room1,room2,room3])
        if room != tag.get_room() :
            return
        print (Bcolors.WARNING+"add sample")
        print (sample)
        if room == room1:
            print ("1 0 0")
        if room == room2:
            print ("0 1 0")
        if room == room3:
            print ("0 0 1")
        print ("end add sample"+Bcolors.ENDC)
        
        
    @staticmethod
    def check_change():
        global ann, debug
        ts = int(time.time())
        logging.debug ("  ----> Analyze Position @ %i" %(ts))
        #todo missing value => missing Tag
        i = 0
        for mac in Tags.tags_dict:
            tag = Tags.tags_dict[mac]
            logging.debug ("\033[95m        analyse tag %s in room %s since %i \033[0m" %(mac,tag.get_room(),tag.get_last_seen()))
            if mac == 'f0:46:00:0b:8b:01' :
                logging.debug ("  special    analyse tag %s in room %s since %i"%(mac,tag.get_room(),tag.get_last_seen()))
                
            #mac = 'f0:46:00:0b:8b:01'
            sample = [AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi,AnalyzeRips._missingRssi]
            
            first = tag.first_rssi()
            if first == []:
                if mac == 'f0:46:00:0b:8b:01' :
                    print(" no rssi for this tag")
                logging.debug("        no rssi for this Tag")
                logging.info (" === tag \033[92m %s \033[0m - is missing from \033[94m %i (max %i)\033[0m" %(tag.get_mac(),tag.get_last_seen(),tag.get_max_delay()))
                continue
            deltat = ts-first[1]
            if (deltat > 4*AnalyzeRips.__deltat) or ((deltat > 3*AnalyzeRips.__deltat) and (tag.count_rssi() > 3)) :
                if mac == 'f0:46:00:0b:8b:01' :
                    print(" build sample this tag",mac)
                values = tag.get_rssi()
                for value in values :
                    antenna,timestamp,rssi = value
                    deltat = ts-timestamp
                    index = Antennas.ANTENNAS.index(antenna) * len(Antennas.ANTENNAS)
                    if deltat > 2*AnalyzeRips.__deltat :
                        sample[index+2] = rssi
                    elif deltat > AnalyzeRips.__deltat :
                        sample[index+1] = rssi
                    else :
                        sample[index] = rssi
                
                #correction because of missing rssi values    
                for antenna in Antennas.ANTENNAS:
                    index = Antennas.ANTENNAS.index(antenna) * len(Antennas.ANTENNAS)   
                    #print("correction start ",antenna,index) 
                    if sample[index+1] == AnalyzeRips._missingRssi and sample[index] != AnalyzeRips._missingRssi and sample[index+2] != AnalyzeRips._missingRssi :
                        logging.debug("        ** correction add missing value @ t0+1 for antenna ",antenna)
                        print(Bcolors.WARNING+"        ** correction add missing value @ t0+1 for antenna ",antenna+Bcolors.ENDC)
                        sample[index+1] = int((sample[index] + sample[index+2]) / 2)
                        
                    if sample[index] == AnalyzeRips._missingRssi and sample[index+1] == AnalyzeRips._missingRssi and sample[index+2] != AnalyzeRips._missingRssi :
                        logging.debug("        ** correction remove oldest rssi value @ t0+2 for antenna ",antenna)
                        print(Bcolors.WARNING+"        ** correction remove oldest rssi value @ t0+2 for antenna "+antenna+Bcolors.ENDC)
                        sample[index+2] = AnalyzeRips._missingRssi
                    
                tag.remove_first_rssi()
                if debug or (mac == 'f0:46:00:0b:8b:01') :
                    print("        corrected sample for tag =",sample,mac)
                positions = ann.run(sample)
                score = max(positions)
                
                if score > 0.9 and max(sample) != AnalyzeRips._missingRssi:
                    skipped = False
                    if min(sample) == AnalyzeRips._missingRssi:
                        '''
                        for antenna in Antennas.ANTENNAS :
                            rssiMin = min([sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)],sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)+1],sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)+2]])
                            rssiMax = max([sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)],sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)+1],sample[Antennas.ANTENNAS.index(antenna)*len(Antennas.ANTENNAS)+2]])
                            if rssiMin == rssiMax :
                                continue
                            if rssiMin == AnalyzeRips._missingRssi :
                                skipped = True
                                #print("       \033[91m sample skipped max, min \033[0m",rssiMax,rssiMin,antenna)
                                break    
                        '''       
                        if skipped :    
                            print("       \033[91m sample skipped with missing value = \033[0m",sample)
                        else :
                            room = Rooms.LOCATIONS[positions.index(score)]
                            previous_room = tag.get_room()
                            if previous_room != room:
                                tag.set_room(room)
                                AnalyzeRips.auto_learn(tag,sample)
                                logging.info (" === new location for %s is \033[92m %s \033[0m - old \033[94m %s \033[0m" %(tag.get_mac(),room,previous_room))
                    else:
                        room = Rooms.LOCATIONS[positions.index(score)]
                        previous_room = tag.get_room()
                        if previous_room != room:
                            tag.set_room(room)
                            AnalyzeRips.auto_learn(tag,sample)
                            logging.info (" === new location for %s is \033[92m %s \033[0m - old \033[94m %s \033[0m" %(tag.get_mac(),room,previous_room))
                        
                elif max(sample) == AnalyzeRips._missingRssi:
                    tag.set_room(Rooms.MISSING)
                else :
                    if debug:
                        print("       \033[91m sample undetermined = \033[0m",sample)
                    ann.add_undetermined_sample(sample, positions)
                    
                while True:
                    first = tag.first_rssi()
                    if first == [] :
                        break
                    deltat = ts-first[1]
                    if deltat > 3*AnalyzeRips.__deltat :
                        #if debug:
                            #print ("        remove old values",first)
                        tag.remove_first_rssi()
                    else:
                        break
            #logging.info("        finish analyze tag, go to next "+mac)
            i +=1
            logging.info ("~~ %i ~~ tag \033[94m %s  \033[0m in room \033[94m %s  \033[0m , last seen  \033[94m %i s (max %i s) \033[0m " %(i,mac,tag.get_room(),ts - tag.get_last_seen(),tag.get_max_delay()))
        logging.info("  ####    finish analyze all tags, summarize now  #### ")
        '''
        i=0
        for mac in Tags.tags_dict:
            i += 1
            tag = Tags.tags_dict[mac]
            logging.info ("~~ %i ~~ tag \033[94m %s  \033[0m in room \033[94m %s  \033[0m , last seen  \033[94m %i s (max %i s) \033[0m " %(i,mac,tag.get_room(),ts - tag.get_last_seen(),tag.get_max_delay()))
            #logging.info ("        ~~~~~ "+Bcolors.OKBLUE+ " %s in room %s "+Bcolors.ENDC+" - last seen %i " %(mac,tag.get_room(),tag.get_last_seen()))
        '''

def start_rips_server(host,port):

    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT state, without waiting for its natural timeout to expire
    #logging.debug("Socket created host %s port %i:" %(host,port))

    try:
        soc.bind((host, port))
    except:
        logging.critical("Bind failed. Error : " + str(sys.exc_info())+Bcolors.ENDC)
        sys.exit()

    soc.listen(5)       # queue up to 5 requests
    logging.info("Socket now listening antennas host %s port %i" %(host,port))

    # infinite loop- do not reset for every requests
    while True:
        connection, address = soc.accept()
        ip, port = str(address[0]), str(address[1])
        
        try:
            Thread(target=client_rips_thread, args=(connection, ip, port)).start()
        except:
            logging.error(Bcolors.FAIL+"Thread did not start."+Bcolors.ENDC)
            traceback.print_exc()

    soc.close()


def client_rips_thread(connection, ip, port, max_buffer_size = 5120):
    global status
    is_active = True

    while is_active:
        client_input = receive_input(connection, max_buffer_size)

        if client_input == False or "--quit--" in client_input:
            logging.debug("Client is requesting to quit")
            connection.close()
            logging.debug("Connection " + ip + ":" + port + " closed")
            is_active = False
        else:
            #logging.debug("Processed result: {}".format(client_input))
            if status == "run" :
                connection.sendall("-".encode("utf8"))
            elif status == "stop" :
                connection.sendall("--stop--".encode("utf8"))
            elif status == "scan" :
                connection.sendall("-".encode("utf8"))
            elif status == "filter" :
                connection.sendall("--filter--,f0:46:00:0b:8b:01".encode("utf8"))
            #connection.sendall("stop".encode("utf8"))

def receive_input(connection, max_buffer_size):
    client_input = connection.recv(max_buffer_size)
    client_input_size = sys.getsizeof(client_input)
    result = -2
    if client_input_size > max_buffer_size:
        logging.error("The input size is greater than expected {}".format(client_input_size))
        result = -1
        
    if client_input_size > 0:
        decoded_input = client_input.decode("utf8").rstrip()  # decode and strip end of line
        result = process_input(decoded_input)

    return result

def write_buffer(queue):
    global mutex
    logging.debug("List and clear the queue, size = %i"% (len(queue)))
    file = open(CAPTURE_FILE,"a")
    mutex.acquire()
    for data in list(queue):
        #logging.debug('Tag %s seen @ %i - rssi= %i from %s',data[1],data[2],data[3],data[0])
        if len(data) == 4 :
            file.write(str(data[1])+","+str(data[2])+","+str(data[3])+","+str(data[0])+"\n")
        else :
            logging.debug("error : remote antenna is not compliant - invalid data : index should be 4 but is %i",len(data))
    
    queue.clear()
    mutex.release() 
    file.close() 


def process_input(input_str):
    global queue, MAX_ITEM, mode, mutex
    
    #logging.debug("Processing the input received from client",input_str)
    ts = int(time.time())
    if "--" in input_str:
        return input_str
    #data = json.loads(input_str)
    try:
        antenna,mac,timestamp,rssi = json.loads(input_str)
    except :
        return False
    
    logging.debug('Tag %s seen @ %i - rssi= %i from %s',mac,timestamp,rssi,antenna)
    #logging.debug('Tag %s seen @ %i - rssi= %i from %s',data[1],data[2],data[3],data[0])
    if ts != timestamp:
        #logging.debug ("timestampSRV=",ts)
        pass
    
    if mode == "Analyze" :
        if mac not in Tags.tags_dict:
            tag = Tags(mac)
        else :
            tag = Tags.tags_dict[mac]
        tag.add_rssi(antenna, timestamp, rssi)
    
    if mode == 'Learn':
        mutex.acquire()
        queue.append([antenna,tag,timestamp,rssi])
        mutex.release()
        if len(queue) > MAX_ITEM:
            write_buffer(queue)
        
    return "Decode= " + str(input_str).upper()


class MyTimer: 
    def __init__(self, tempo, target, args= [], kwargs={}): 
        self._target = target 
        self._args = args 
        self._kwargs = kwargs 
        self._tempo = tempo 
  
    def _run(self): 
        self._timer = Timer(self._tempo, self._run) 
        self._timer.start() 
        self._target(*self._args, **self._kwargs) 
  
    def start(self): 
        self._timer = Timer(self._tempo, self._run) 
        self._timer.start() 
  
    def stop(self): 
        self._timer.cancel() 


def analyze_position(queue):
    #logging.debug('analyse change')
    AnalyzeRips.check_change()
    



class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def init_rips_listen_server():
    global queue, status
    host = "127.0.0.1"
    host = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)),s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET,socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
    port = 7008         # arbitrary non-privileged port

    queue = deque()
    file = open(CAPTURE_FILE,"w")
    file.close()
    
    try:
        Thread(target=start_rips_server, args=(host,port)).start()
    except:
        logging.error(Bcolors.FAIL+"Thread did not start."+Bcolors.ENDC)
        traceback.print_exc()
    

if __name__ == "__main__":
    logging.info(Bcolors.HEADER+"************************************************")
    logging.info(Bcolors.HEADER+"*                                              *")
    logging.info(Bcolors.HEADER+"*       rips : listen antennas                 *")
    logging.info(Bcolors.HEADER+"*              analyze position of tags        *")
    logging.info(Bcolors.HEADER+"*                                              *")
    logging.info(Bcolors.HEADER+"************************************************"+Bcolors.ENDC)
    
    
    init_rips_listen_server()
    
    periodic = MyTimer(4.0, analyze_position, [queue])
    periodic.start()
    
    time.sleep(2)
    logging.info(Bcolors.HEADER+"Enter 'quit' to exit"+Bcolors.ENDC)
    command = input(" -> ").lower()
    
    while command != 'quit':
        print ("command=",command)
        if command == "stop" :
            status = "stop"
        elif command == "scan" :
            status = "scan"
        elif command == "filter" :
            status = "filter"
        command = input(" -> ").lower()
        
    if mode == "Learn":
        write_buffer(queue)
        count = file_len(CAPTURE_FILE)
        logging.info (Bcolors.BOLD+"recorded count =",count)
    
    periodic.stop()
    '''
    for mac in Tags.tags_dict :
        #logging.debug ("tag mac %s",mac)
        tag = Tags.tags_dict[mac]
        if debug:
            print ("values =",tag)
            
        #tag.list_rssi()
        print (tag.list_historic())
    '''  
    for sample in ann.undetermined_sample :
        if min(sample) != AnalyzeRips._missingRssi :
            print (Bcolors.FAIL+"undetermined sample without missing value"+Bcolors.ENDC,sample)
            
    for sample in ann.undetermined_sample :
        if min(sample) == AnalyzeRips._missingRssi :
            print (Bcolors.FAIL+"undetermined sample with missing value"+Bcolors.ENDC,sample)
        
    logging.debug(Bcolors.OKGREEN+"exit listening"+Bcolors.ENDC)
    os._exit(0)
