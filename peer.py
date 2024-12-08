#peer.py

import os
import socket
import threading
import uuid

class peer:
    def __init__(self, shared_dir, host = '127.0.0.1', port = 8000):
        self.peer_id = str(uuid.uuid4())    # unique id assigned for each peer
        self.shared_dir = shared_dir
        self.file_list = os.listdir(shared_dir) # list of shared files
        self.host = host
        self.port = port
        self.known_peers = []   # list of other peers (IP, port)
        
if __name__ == "__main__":
    print("Hi")