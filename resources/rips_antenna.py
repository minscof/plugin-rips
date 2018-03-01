#!/usr/bin/python
''' Bluetooth scanner inspired by and modified to run with php script for non BLE devices
   Author: jmleglise
   Date: 25-May-2016
   Description : Test yours beacon 
   URL : https://github.com/jmleglise/mylittle-domoticz/edit/master/Presence%20detection%20%28beacon%29/test_beacon.py
   Version : 1.0

 Copyright (c) 2017-05 Diving-91 (User:diving91 https://www.jeedom.fr/forum/)
 URL: https://github.com/diving91/Bluetooth-scanner

 MIT License
 Copyright (c) 2017 

 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.'''

''' DESCRIPTION
 This script will send data to the main php script each time a BLE device is advertising
        data is a json of [[bdaddr , timestamp last seen],[...]]
 Works well with Nut mini BLE devices: (https://goo.gl/l36Gtz)
 
 USAGE
 $ python rips_antenna.py hciAdapterID debug jsonTagsBDaddr antenna gateway
        Example: sudo python rips_antenna.py 0 1 [\"EF:A2:C5:EB:A3:2F\",\"FF:FE:8A:40:FA:97\"]
 $ python BLE.py kill
        This will kill the previously launched BLE.py processes
'''
import os
import sys
import pwd
import struct
import logging
import json
import bluetooth._bluetooth as bluez
import time

import socket
from threading import Thread

LE_META_EVENT = 0x3e
OGF_LE_CTL=0x08
OCF_LE_SET_SCAN_ENABLE=0x000C
EVT_LE_CONN_COMPLETE=0x01
EVT_LE_ADVERTISING_REPORT=0x02

def packed_bdaddr_to_string(bdaddr_packed):
    return ':'.join('%02x'%i for i in struct.unpack("<BBBBBB", bdaddr_packed[::-1]))

def hci_toggle_le_scan(sock, enable):
    cmd_pkt = struct.pack("<BB", enable, 0x00)
    bluez.hci_send_cmd(sock, OGF_LE_CTL, OCF_LE_SET_SCAN_ENABLE, cmd_pkt)
    
def Initialize():    
        TAG_DATA = [] # Example [["EF:A2:C5:EB:A3:2F",0,-200],["FF:FE:8A:40:FA:97",0,-200]] - [bdaddr , timestamp last seen, last rssi] - imported from argv[3]
        
        me = os.path.basename(__file__)
        
        # Check 3 args are supplied or 1 arg 'kill'
        if not(len(sys.argv) == 6) and not(len(sys.argv) == 2 and sys.argv[1] =='kill'):
            print("ERROR: Please use arguments")
            print("$ python "+me+" adapterNb debug jsonTagsBdaddr antenna gateway")
            print("$ python "+me+" kill")
            sys.exit(1)
        elif len(sys.argv) == 6: # ARG2: define logging level
            FORMAT = '%(asctime)s - %(message)s'
            if sys.argv[2] == "1":
                logLevel=logging.DEBUG
                logging.basicConfig(format=FORMAT,level=logLevel)
            elif sys.argv[2] == "0":
                logLevel=logging.CRITICAL    
                logging.basicConfig(format=FORMAT,level=logLevel)
            else:
                print("ERROR: Wrong logging level supplied - Use 0 or 1")
                sys.exit(1)
        
        # ARG1: Kill BLE scanner or check hci adapter
        if sys.argv[1] == "kill": #Kill mode
            x = os.popen("ps aux | grep " + me + " | grep -v grep| grep -v sudo | awk '{print $2}'").read().splitlines() # all processes
            x = list(set(x).difference([str(os.getpid())])) # all processes but current one
            if x:
                x = int(x[0]) # convert to pid
                print('Kill %s process %i'%(me,x))
                os.system("sudo kill %i" % (x))
                sys.exit(0)
            else:
                print('There is no %s process to kill'%(me))
                sys.exit(0)
        else: # define hci adapter
            try:
                hciId = int(sys.argv[1]) # 0 for hci0
                logging.debug('Will Use hci adapter hci%s'%(sys.argv[1]))
            except:
                logging.critical('ERROR - Wrong HCI adapter number supplied: %s'%(sys.argv[1]))
                sys.exit(1)
                
        # ARG3: json BLE TAGs mac address
        try:
            tags = json.loads(sys.argv[3])
            for tag in tags:
                #TAG_DATA.append([tag.encode('ascii', 'ignore'),0,-200])
                TAG_DATA.append([tag,0,-200])
            logging.debug('Will scan %s tag(s) with bdaddr %s'%(sys.argv[3].count(":")/5,sys.argv[3]))
        except:
            print('ERROR: Wrong last argument json for TAGS - Use [\\"xx:yy:zz:vv:ww:zz\\",..]')
            logging.critical('ERROR - Wrong json for TAGS: %s'%sys.argv[3])
            sys.exit(1)
        #TAG_DATA=[["F0:46:00:0B:8B:01",0,-200],["E8:4E:BC:87:86:9F",0,-200]]
        
        # ARG4: name of the antenna
        try:
            antenna = sys.argv[4]
            logging.debug('Will use antenna name %s '%sys.argv[4])
        except:
            print('ERROR: Wrong antenna name')
            logging.critical('ERROR - Wrong antenna name: %s'%sys.argv[4])
            sys.exit(1)
            
        # ARG5: name or Ip address of the gateway that collects data
        try:
            gateway = sys.argv[5]
            logging.debug('Will use antenna name %s '%sys.argv[5])
        except:
            print('ERROR: Wrong gateway name or ip')
            logging.critical('ERROR - Wrong gateway name or ip: %s'%sys.argv[5])
            sys.exit(1)
            
        return [hciId,TAG_DATA,antenna,gateway]

class ListenBle(Thread):
    
    def __init__(self, hciId, TAG_DATA, gateway):
        Thread.__init__(self)
        self.hciId = hciId
        self.TAG_DATA = TAG_DATA
        #self.TAG_DATA = [["F0:46:00:0B:8B:01",0,-200]]
        for tag in self.TAG_DATA:
            print ("mac filter=",tag[0].lower())
        self.gateway = gateway
       
       
    def run(self):   
        # MAIN part of the script
        # Connect to hci adapter
        print('début de listen BLE')
        
        
        try:
            sock = bluez.hci_open_dev(self.hciId)
            logging.debug('Connected to bluetooth adapter hci%i',self.hciId)
        except:
            logging.critical('Unable to connect to bluetooth device hci%i...',self.hciId)
            sys.exit(1)
        
        # Enable LE scan
        hci_toggle_le_scan(sock, 0x01)
        # Infinite loop to listen socket
        while True:
            old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)
            flt = bluez.hci_filter_new()
            bluez.hci_filter_all_events(flt)
            bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
            sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )
        
            pkt = sock.recv(255)
            
            ptype, event, plen = struct.unpack("BBB", pkt[:3])
        
            if event == LE_META_EVENT:
                #print ('packet=',pkt)
                #subevent=pkt[3]
                subevent, = struct.unpack("B", pkt[3:4])
                pkt = pkt[4:]
                if subevent == EVT_LE_CONN_COMPLETE:
                    le_handle_connection_complete(pkt)
                elif subevent == EVT_LE_ADVERTISING_REPORT:
                    num_reports = struct.unpack("B", pkt[0:1])[0]
                    for i in range(0, num_reports):
                        macAdressSeen=packed_bdaddr_to_string(pkt[3:9])
                        #print('mac=',macAdressSeen)
                        ts = int(time.time()) # time of event
                        for tag in self.TAG_DATA:
                            #print('    check mac=',tag[0].lower())
                            if macAdressSeen.lower() == tag[0].lower():
                                #print('mac=',macAdressSeen)
                                #print ('packet=',pkt)
                                # More than 2 seconds from last seen, so we can call php callback. This prevent overload from high freq advertising devices
                                inc=0
                                if ts > tag[1]+inc:
                                    tag[1]=ts # update lastseen
                                    rssi, = struct.unpack("b", pkt[len(pkt)-1:len(pkt)])
                                    tag[2] = rssi
                                    #print ('packet et rssi=',pkt,rssi)
                                    logging.debug('Tag %s seen @ %i - rssi= %i',tag[0],tag[1],rssi)
                                    #jsonTag = json.dumps([tag[0],tag[1],tag[2]],separators=(',', ':')) # json encode TAG_DATA list
                                    #self.gateway.Send(jsonTag)
                                    self.gateway.Send([tag[0],tag[1],tag[2]])
                                    
            sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )


class push:
    
    def __init__(self,host,port,antenna):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.antenna = antenna

    def Connect(self):
        if self.host == None:
            self.host = "127.0.0.1"
        if self.port == None:
            self.port = 7008
        if self.antenna == None:
            self.antenna = "myAntenna"
    
        try:
            self.soc.connect((self.host, self.port))
        except:
            print("Connection error host %s port %i" % (self.host,self.port))
            sys.exit()
            
    def Disconnect(self):
        self.soc.send(b'--quit--')
        
    def Send(self,message):
        #jsonTag = json.dumps([tag[0],tag[1],tag[2]],separators=(',', ':'))
        json.dumps([self.antenna,message[0],message[1],message[2]],separators=(',', ':'))
        self.soc.sendall(json.dumps([self.antenna,message[0],message[1],message[2]],separators=(',', ':')).encode("utf8"))
        if self.soc.recv(5120).decode("utf8") == "-":
            pass        # null operation

def Main():
    
    values=Initialize()
    gateway = push(values[3],7008,values[2])
    gateway.Connect()
    #TAG_DATA=[["F0:46:00:0B:8B:01",0,-200],["E8:4E:BC:87:86:9F",0,-200]]
    t=ListenBle(values[0],values[1],gateway)
    t.start()
    
    print("Enter 'quit' to exit")
    message = input(" -> ")

    while message != 'quit':
        gateway.Send(message)
        message = input(" -> ")

    gateway.Disconnect()
    print("exit scanning")
    os._exit(0)

if __name__ == "__main__":
    Main()