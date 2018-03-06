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
CAPTURE_FILE = "captureRssi.txt"
MAX_ITEM = 2000
queue = None
#mode = 'Learn'
mode = 'Analyze'
mutex = Lock()
status = "scan"



if debug :
    logLevel=logging.DEBUG
    logging.basicConfig(format=FORMAT,level=logLevel)
else :
    logLevel=logging.CRITICAL    
    logging.basicConfig(format=FORMAT,level=logLevel)

class Neuron:
    def __init__(self):
        self.ann = libfann.neural_net()
        self.ann.create_from_file("training_result")
        
    def run(self,sample):
        result = self.ann.run(sample)
        print (result)
        return result

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
    def __init__(self,mac):
        self.mac = mac
        self.position = Rooms.UNKNOWN
        self.rssiValues = []
        Tags.tags_dict[mac]=self
    
    def get_mac(self):
        return self.mac
    
    def set_room(self,room):
        self.position = room
    
    def get_room(self):
        return self.position
    
    def add_rssi(self,antenna,timestamp,rssi):
        global mutex
        mutex.acquire()
        self.rssiValues.append([antenna, timestamp,rssi])
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
        for tab in self.rssiValues :
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


class AnalyzeRips:
    __deltat = 5
    __missingRssi = -110
        
    @staticmethod
    def check_change():
        global ann
        ts = int(time.time())
        print ('Analyze Position @ ',ts)
        for mac in Tags.tags_dict:
            tag = Tags.tags_dict[mac]
            print ("analyse tag %s in room %s",mac,tag.get_room())
            
            #mac = 'f0:46:00:0b:8b:01'
            first = tag.first_rssi()
            if first == []:
                print("no rssi for this Tag")
                break
            deltat = ts-first[1]
            sample = [AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi,AnalyzeRips.__missingRssi]
            if (deltat > 4*AnalyzeRips.__deltat) or ((deltat > 3*AnalyzeRips.__deltat) and (tag.count_rssi() > 3)) :
                values = tag.get_rssi()
                for value in values :
                    antenna,timestamp,rssi = value
                    deltat = ts-timestamp
                    index = Antennas.ANTENNAS.index(antenna) *3
                    if deltat > 2*AnalyzeRips.__deltat :
                        sample[index+2] = rssi
                    elif deltat > AnalyzeRips.__deltat :
                        sample[index+1] = rssi
                    else :
                        sample[index] = rssi
                    
                    '''
                    for i in [index+2,index+1,index]:
                        if sample[i] == AnalyzeRips.__missingRssi:
                            sample[i] = rssi
                            break
                        else :
                            if i == index+2:
                               sample[i] = rssi 
                    '''
                if sample[index+1] == AnalyzeRips.__missingRssi and sample[index] != AnalyzeRips.__missingRssi and sample[index+2] != AnalyzeRips.__missingRssi :
                    print("** correction add missing value @ t0+1")
                    sample[index+1] = int((sample[index] + sample[index+2]) / 2)
                    
                tag.remove_first_rssi()
                print("sample =",sample)
                positions = ann.run(sample)
                score = max(positions)
                if score > 0.9:
                    room = Rooms.LOCATIONS[positions.index(score)]
                    if tag.get_room() != room:
                        tag.set_room(room)
                        print (" ======= new location for %s is %s",tag.get_mac(),room)
                    elif max(sample) == AnalyzeRips.__missingRssi:
                        tag.set_room(Rooms.MISSING)
                    else :
                        tag.set_room(Rooms.UNKNOWN)
                
                while True:
                    first = tag.first_rssi()
                    if first == [] :
                        break
                    deltat = ts-first[1]
                    if deltat > 3*AnalyzeRips.__deltat :
                        print ("remove old values",first)
                        tag.remove_first_rssi()
                    else:
                        break
                print("exit check change")
                        
                    
                         
                
    


def start_rips_server():
    host = "127.0.0.1"
    port = 7008         # arbitrary non-privileged port

    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT state, without waiting for its natural timeout to expire
    print("Socket created host %s port %i:",host,port)

    try:
        soc.bind((host, port))
    except:
        print("Bind failed. Error : " + str(sys.exc_info())+Bcolors.ENDC)
        sys.exit()

    soc.listen(5)       # queue up to 5 requests
    print("Socket now listening")

    # infinite loop- do not reset for every requests
    while True:
        connection, address = soc.accept()
        ip, port = str(address[0]), str(address[1])
        print("Connected with " + ip + ":" + port)

        try:
            Thread(target=client_rips_thread, args=(connection, ip, port)).start()
        except:
            print(Bcolors.FAIL+"Thread did not start."+Bcolors.ENDC)
            traceback.print_exc()

    soc.close()


def client_rips_thread(connection, ip, port, max_buffer_size = 5120):
    global status
    is_active = True

    while is_active:
        client_input = receive_input(connection, max_buffer_size)

        if "--quit--" in client_input:
            print("Client is requesting to quit")
            connection.close()
            print("Connection " + ip + ":" + port + " closed")
            is_active = False
        else:
            #print("Processed result: {}".format(client_input))
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
        print("The input size is greater than expected {}".format(client_input_size))
        result = -1
        
    if client_input_size > 0:
        decoded_input = client_input.decode("utf8").rstrip()  # decode and strip end of line
        result = process_input(decoded_input)

    return result

def write_buffer(queue):
    global mutex
    print ("List and clear the queue")
    logging.debug("List and clear the queue, size = %i",len(queue))
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
    
    #print("Processing the input received from client",input_str)
    ts = int(time.time())
    if "--" in input_str:
        return input_str
    #data = json.loads(input_str)
    antenna,mac,timestamp,rssi = json.loads(input_str)
    logging.debug('Tag %s seen @ %i - rssi= %i from %s',mac,timestamp,rssi,antenna)
    #logging.debug('Tag %s seen @ %i - rssi= %i from %s',data[1],data[2],data[3],data[0])
    if ts != timestamp:
        #print ("timestampSRV=",ts)
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
        
    #logging.debug('len queue',len(queue))
    #print ("len queue %i max %i",len(queue),MAX_ITEM)
        
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
    #print('analyse change')
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
    queue = deque()
    file = open(CAPTURE_FILE,"w")
    file.close()
    
    try:
        Thread(target=start_rips_server, args=()).start()
    except:
        print(Bcolors.FAIL+"Thread did not start."+Bcolors.ENDC)
        traceback.print_exc()
    

if __name__ == "__main__":
    init_rips_listen_server()
    
    periodic = MyTimer(5.0, analyze_position, [queue])
    periodic.start()
    
    time.sleep(2)
    print(Bcolors.HEADER+"Enter 'quit' to exit"+Bcolors.ENDC)
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
        print (Bcolors.BOLD+"recorded count =",count)
    
    periodic.stop()
    for mac in Tags.tags_dict :
        print ("tag mac %s",mac)
        tag = Tags.tags_dict[mac]
        print ("values =",tag)
        tag.list_rssi()
    
    
    print(Bcolors.OKGREEN+"exit listening"+Bcolors.ENDC)
    os._exit(0)
