import os
import sys
import traceback
import socket
from threading import Thread, Lock
import json
import time
from collections import deque
import logging


debug = True
FORMAT = '%(asctime)s - %(message)s'
CAPTURE_FILE = "captureRssi.txt"
MAX_ITEM = 2000
queue = None
mode = 'Learn'
#mode = 'Analyze'
mutex = Lock()
status = "scan"



if debug :
    logLevel=logging.DEBUG
    logging.basicConfig(format=FORMAT,level=logLevel)
else :
    logLevel=logging.CRITICAL    
    logging.basicConfig(format=FORMAT,level=logLevel)


def start_rips_server():
    host = "127.0.0.1"
    port = 7008         # arbitrary non-privileged port

    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT state, without waiting for its natural timeout to expire
    print("Socket created port:",port)

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
        
def analyze_position(queue):
    mutex.acquire()
    
    mutex.release()
    return

def process_input(input_str):
    global queue, MAX_ITEM, mode, mutex
    #print("Processing the input received from client",input_str)
    ts = int(time.time())
    if "--" in input_str:
        return input_str
    data = json.loads(input_str)
    #logging.debug('Tag %s seen @ %i - rssi= %i from %s',data[1],data[2],data[3],data[0])
    if ts != data[2]:
        #print ("timestampSRV=",ts)
        pass
    mutex.acquire()
    queue.append(data)
    mutex.release()
    if mode == "Analyze" :
        analyze_position(queue)
    #logging.debug('len queue',len(queue))
    #print ("len queue %i max %i",len(queue),MAX_ITEM)
    if len(queue) > MAX_ITEM:
        if mode == 'Learn':
            write_buffer(queue)
        else :
            mutex.acquire()
            queue.popleft()
            mutex.release()
            
    return "Decode= " + str(input_str).upper()


def file_len(fname):
    i=-1
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1

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
    #start_rips_server()
    

if __name__ == "__main__":
    init_rips_listen_server()
    
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
    
    
    print(Bcolors.OKGREEN+"exit listening"+Bcolors.ENDC)
    os._exit(0)
