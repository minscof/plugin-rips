#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import logging
import argparse
import subprocess
from time import time, localtime, strftime, sleep
import urllib.request, urllib.error, urllib.parse
#import exceptions
from threading import Thread, Timer
from http.server import BaseHTTPRequestHandler, HTTPServer
import rips_listen_antenna


__version__='0.1'

reqlog = logging.getLogger("requests.packages.urllib3.connectionpool")
reqlog.disabled = True


level = logging.DEBUG
#if getattr(args, 'debug', False):
#    level = logging.DEBUG
logging.basicConfig(level=level)

if len(sys.argv) > 1:
    PORT = int(sys.argv[1])
else:
    PORT = 7000

# jeedomSystem=${2}
if len(sys.argv) > 2:
    jeedomSystem = sys.argv[2]
else:
    jeedomSystem = "Raspberry"

# jeedomSystem=${3}
if len(sys.argv) > 3:
    arg3 = sys.argv[3]
else:
    arg3 = None

# jeedomIP=${4}
if len(sys.argv) > 4:
    jeedomIP = sys.argv[4]
else:
    jeedomIP = "127.0.0.1"

# jeedomApiKey=${5}
if len(sys.argv) > 5:
    jeedomApiKey = sys.argv[5]
else:
    jeedomApiKey = "jeedomApiKey"


jeedomCmd = "http://" + jeedomIP + "/core/api/jeeApi.php?apikey=" + jeedomApiKey + '&type=rips&value='


time_start = time()
print('Server started at ', strftime("%a, %d %b %Y %H:%M:%S +0000", localtime(time_start)), 'listening on port ', PORT)  

myHttpServer = None
stopMyHttpServer = None
      

def init_http_server():
    
    try:
        Thread(target=start_http_server, args=(HTTPServer,JeedomHandler,PORT)).start()
    except:
        print(Bcolors.FAIL+"Http server did not start."+Bcolors.ENDC)
        traceback.print_exc()
        
class JeedomHandler(BaseHTTPRequestHandler):
    def _set_polling(self):
        # initialization.
        self.polling = MyTimer(5.0, polling, [self,"polling "])
        print ("affiche polling...")
         
    def _set_headers(self,result,content_type):
        self.send_response(result)
        self.send_header('Content-type', content_type)
        self.end_headers()

    def do_GET(self):
        print ('get request')
        
        #self.wfile.write(bytes("<html><body><h1>hi!</h1></body></html>", "utf8"))
        result,content_type,data = self.process(self.path)
        self._set_headers(result,content_type)
        self.wfile.write(bytes(data, "utf8"))
        

    def do_HEAD(self):
        self._set_headers()
        
    def do_POST(self):
        # Doesn't do anything with posted data
        self._set_headers()
        self.wfile.write(bytes("<html><body><h1>POST!</h1></body></html>", "utf8")) 
        
        
    def process(self, path):
        #global myHttpServer
        print ("receive request=",path)
        #cmd = environ['PATH_INFO'].strip('/')
        path = path.strip('/')
        arg = None
        if '?' in path :
            cmd,arg = path.split('?')
        else :
            cmd = path
        
        key = ''
        value = ''
        key2 = ''
        value2 = ''
        if arg:
            options = arg.split('&') 
            key = options[0].rpartition('=')[0]
            value = urllib.parse.unquote(options[0].rpartition('=')[2])
            if len(options) == 2:
                key2 = options[1].rpartition('=')[0]
                value2 = urllib.parse.unquote(options[1].rpartition('=')[2])
            
        print('cmd=', cmd, ' arg ', arg, ' key ', key, ' value ', value, ' key2 ', key2, ' value2 ', value2)
        content_type = "text/javascript"
        content_type = "text/html"

        if not cmd:
            return [200,content_type,'<h1>Welcome. Try a command ex : scan, stop, start.</h1>']
            
        if cmd == 'dump':
            print("********** Dump - equipments :  All  **********")
            content_type = "text/javascript"
            data = '{"result":"ok"}'
            return [200,content_type,data]
            
        if cmd == 'startPolling':
            self.polling.start()
            content_type = "text/javascript"
            data = '{"result":"ok","command":"startPolling"}'
            return [200,content_type,data]
        
        if cmd == 'stopPolling':
            if self.polling != '':
                self.polling.stop()
            content_type = "text/javascript"
            data = '{"result":"ok"}'
            return [200,content_type,data]

        if cmd == 'test':
            print("EVENT to notify send command", jeedomCmd + 'test')  
            a = urllib.request.urlopen(jeedomCmd + 'test').read()
            content_type = "text/javascript"
            data = '{"result":"ok"}'
            return [200,content_type,data]
            
        if cmd.startswith('stop') or cmd == 'stop':
            print('arrêt du serveur demandé')
            content_type = "text/javascript"
            data = '{"result":"ok"}'
            return [200,content_type,data]
            
        print("Command not recognized :", cmd)
        
        content_type = "text/javascript"
        data = '{"result":"notfound"}'
        return [200,content_type,data]

def start_http_server(server_class=HTTPServer, handler_class=JeedomHandler, port=PORT):
    global myHttpServer
    print(Bcolors.HEADER+"start start_http_server"+Bcolors.ENDC)
    server_address = ('', port)
    handler_class._set_polling(handler_class)
    
    
    print('Listening on http://127.0.0.1:%s ' % PORT)
  
    print("EVENT to notify start server", jeedomCmd + 'start')
    #urllib2.urlopen(jeedomCmd + 'start').read()
    print("EVENT to notify start server", jeedomCmd + 'start - DONE')
    
    try:
  
        myHttpServer = server_class(server_address, handler_class)
        print ('Starting httpd...')
        myHttpServer.serve_forever()
    except (KeyboardInterrupt, SystemExit):
      print('interception signal')
      os._exit(0)


  
def polling(self, unstr):
    global stopMyHttpServer, myHttpServer
    print(unstr, time())
    if stopMyHttpServer is not None:
        myHttpServer.stop()
        print("exit")
        os._exit(0)
        
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

    

 
class Bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
if __name__ == '__main__':
    print(Bcolors.HEADER+"start main"+Bcolors.ENDC)
    init_http_server()
    '''
    
    Specific for this server (rips)
    
    
    '''
    rips_listen_antenna.init_rips_listen_server()
    '''
    '''
    sleep(2)
    
    print('before entering mainloop keyboard')
    runLoop = True
  
    print(Bcolors.HEADER+"Enter 'quit' to exit"+Bcolors.ENDC)
    while runLoop:
      command = input(" -> ").lower()
      if command == 'q' or command == 'quit':
        runLoop = False
      
    print(Bcolors.OKGREEN+"exit rips_server"+Bcolors.ENDC)
    os._exit(0)
    
