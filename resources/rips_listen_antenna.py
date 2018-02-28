import socket
import sys
import traceback
from threading import Thread
import json
import time



def Main():
    start_server()


def start_server():
    host = "127.0.0.1"
    port = 7008         # arbitrary non-privileged port

    soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # SO_REUSEADDR flag tells the kernel to reuse a local socket in TIME_WAIT state, without waiting for its natural timeout to expire
    print("Socket created")

    try:
        soc.bind((host, port))
    except:
        print("Bind failed. Error : " + str(sys.exc_info()))
        sys.exit()

    soc.listen(5)       # queue up to 5 requests
    print("Socket now listening")

    # infinite loop- do not reset for every requests
    while True:
        connection, address = soc.accept()
        ip, port = str(address[0]), str(address[1])
        print("Connected with " + ip + ":" + port)

        try:
            Thread(target=client_thread, args=(connection, ip, port)).start()
        except:
            print("Thread did not start.")
            traceback.print_exc()

    soc.close()


def client_thread(connection, ip, port, max_buffer_size = 5120):
    is_active = True

    while is_active:
        client_input = receive_input(connection, max_buffer_size)

        if "--quit--" in client_input:
            print("Client is requesting to quit")
            connection.close()
            print("Connection " + ip + ":" + port + " closed")
            is_active = False
        else:
            print("Processed result: {}".format(client_input))
            connection.sendall("-".encode("utf8"))


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


def process_input(input_str):
    #print("Processing the input received from client",input_str)
    ts = int(time.time())
    if "--quit--" in input_str:
        return input_str
    data = json.loads(input_str)
    print ("mac=",data[0])
    print ("rssi=",data[2])
    print ("timestampCLI=",data[1])
    if ts != data[1]:
        print ("timestampSRV=",ts)
    
    return "Decode= " + str(input_str).upper()

if __name__ == "__main__":
    Main()