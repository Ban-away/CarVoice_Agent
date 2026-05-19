import os
import re
import requests
import json
import time
import random
import pprint
from time import sleep
import socketio


# 从环境变量获取入口URL，支持动态端口配置
entry_port = os.environ.get('ENTRY_PORT', '8080')
URL = os.environ.get("ENTRY_URL", f"http://127.0.0.1:{entry_port}/request_nlu")

sio = socketio.Client()

@sio.on("connect")
def on_connect():
    print("connected to server")

@sio.on("disconnect")
def on_disconnect():
    print("disconnected to server")

@sio.on("message")
def on_message(data):  
    print('Received message:', data)  

@sio.on("error")
def on_error(e):
    print('Error:', e)  

@sio.on("request_nlu")
def on_response(data):  
    print('Response:', end="")
    data = json.loads(data)
    print(data)


def rand_str(size=6):
    return "".join(random.sample("1234567890zyxwvutsrqponmlkjihgfedcba", size))


if __name__ == "__main__":

    data = {
        "sender_id": rand_str(9)
    }

    sio.connect(URL)

    while True:
        data["trace_id"] = rand_str(9)
        print("enter query: ")
        query = re.sub(r'[\x00-\x1f\x7f]', '', input()).strip()
        data["query"] = query
        data["enable_dm"] = True 
        sio.emit("request_nlu", json.dumps(data, ensure_ascii=False))

    print("done")