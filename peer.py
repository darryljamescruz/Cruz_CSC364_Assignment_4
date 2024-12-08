import os
import socket
import threading
import uuid
import hashlib
import time

CHUNK_SIZE = 1024

class Peer:
    def __init__(self, shared_dir, host='127.0.0.1', port=8000, tracker_host=None, tracker_port=None):
        self.peer_id = str(uuid.uuid4())  # Unique ID for each peer
        self.shared_dir = os.path.join(shared_dir, "shared")  # Subdirectory for shared files
        self.download_dir = os.path.join(shared_dir, "downloads")  # Subdirectory for downloaded files
        self.host = host
        self.port = port
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port

        # Ensure shared and download directories exist
        os.makedirs(self.shared_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

        self.file_list = os.listdir(self.shared_dir)  # List of shared files

    def start_listener(self):
        """Start listening for incoming connections."""
        threading.Thread(target=self._listener_thread, daemon=True).start()
        print(f"Peer {self.peer_id} is listening on {self.host}:{self.port}.")

    def _listener_thread(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            while True:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True).start()

    def _handle_client(self, client_socket, addr):
        """Handle incoming messages."""
        with client_socket:
            data = client_socket.recv(1024).decode()
            print(f"Received: {data} from {addr}.")
            if data.startswith("R|"):  # File request
                _, file_name = data.split("|", 1)
                self._send_file(file_name, client_socket)

    def _send_file(self, file_name, client_socket):
        """Send the requested file to the client in chunks with acknowledgment."""
        retries = 3
        file_path = os.path.join(self.shared_dir, file_name)
        if os.path.exists(file_path):
            checksum = self._compute_checksum(file_path)
            client_socket.sendall(f"T|{checksum}".encode())  # Send file checksum first
            with open(file_path, "rb") as f:
                chunk = f.read(CHUNK_SIZE)
                while chunk:
                    for _ in range(retries):
                        client_socket.sendall(b"C|" + chunk)
                        try:
                            ack = client_socket.recv(CHUNK_SIZE).decode()
                            if ack.startswith("A|"):
                                break
                        except socket.timeout:
                            print("Timeout waiting for acknowledgment. Retrying...")
                    else:
                        print("Failed to transfer chunk after retries.")
                        return
                    chunk = f.read(CHUNK_SIZE)
            print(f"File {file_name} sent successfully.")
        else:
            client_socket.sendall(b"E|File not found.")

    def _compute_checksum(self, file_path):
        """Compute MD5 checksum for the file."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def request_file(self, peer, file_name):
        """Request a file from another peer."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(peer)
                s.sendall(f"R|{file_name}".encode())
                checksum = s.recv(CHUNK_SIZE).decode().split("|")[1]  # Receive checksum

                # Save the file to the downloads folder
                download_path = os.path.join(self.download_dir, file_name)
                with open(download_path, "wb") as f:
                    while True:
                        data = s.recv(CHUNK_SIZE)
                        if not data:
                            break
                        if data.startswith(b"C|"):
                            f.write(data[2:])  # Strip "C|" prefix
                            s.sendall(b"A|Acknowledged")

                # Verify file integrity
                downloaded_checksum = self._compute_checksum(download_path)
                if checksum == downloaded_checksum:
                    print(f"File {file_name} downloaded successfully to {self.download_dir} and verified.")
                else:
                    print(f"File {file_name} failed integrity check.")
            except ConnectionError:
                print(f"Failed to connect to peer {peer}")

    def register_with_tracker(self):
        """Register with the tracker server."""
        if not self.tracker_host or not self.tracker_port:
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((self.tracker_host, self.tracker_port))
                message = f"REGISTER|{self.peer_id}|{self.host}|{self.port}"
                s.sendall(message.encode())
                print("Registered with tracker.")
            except ConnectionError:
                print("Failed to register with tracker.")

    def request_peer_list(self):
        """Query the tracker for the list of peers."""
        if not self.tracker_host or not self.tracker_port:
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((self.tracker_host, self.tracker_port))
                s.sendall(b"GET_PEERS")
                data = s.recv(1024).decode()
                peer_list = data.split("|")
                print("Known peers:", peer_list)
            except ConnectionError:
                print("Failed to fetch peer list from tracker.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a P2P file sharing peer.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to run the peer on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the peer on")
    parser.add_argument("--shared_dir", default="./peer_files", help="Directory for shared and downloaded files")
    parser.add_argument("--tracker_host", help="Tracker host")
    parser.add_argument("--tracker_port", type=int, help="Tracker port")
    args = parser.parse_args()

    peer = Peer(shared_dir=args.shared_dir, host=args.host, port=args.port,
                tracker_host=args.tracker_host, tracker_port=args.tracker_port)
    peer.start_listener()
    peer.register_with_tracker()

    print("Commands:")
    print("1. request <host> <port> <file_name> - Request a file from a peer")
    print("2. get_peers - Fetch peer list from the tracker")
    while True:
        command = input("Enter a command: ")
        if command.startswith("request"):
            _, peer_host, peer_port, file_name = command.split()
            peer.request_file((peer_host, int(peer_port)), file_name)
        elif command == "get_peers":
            peer.request_peer_list()