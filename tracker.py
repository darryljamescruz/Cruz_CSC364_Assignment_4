import socket
import threading

class Tracker:
    def __init__(self, host='127.0.0.1', port=9000):
        self.host = host
        self.port = port
        self.peers = {}  # {peer_id: (host, port)}

    def start(self):
        threading.Thread(target=self._listener_thread, daemon=True).start()
        print(f"Tracker is running on {self.host}:{self.port}")

    def _listener_thread(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            while True:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True).start()

    def _handle_client(self, client_socket, addr):
        """Handle messages from peers."""
        with client_socket:
            data = client_socket.recv(1024).decode()
            if data.startswith("REGISTER|"):
                self._register_peer(data)
            elif data.startswith("GET_PEERS"):
                self._send_peer_list(client_socket)

    def _register_peer(self, message):
        """Register a new peer."""
        _, peer_id, host, port = message.split("|")
        self.peers[peer_id] = (host, int(port))
        print(f"Registered peer {peer_id} at {host}:{port}")

    def _send_peer_list(self, client_socket):
        """Send the list of registered peers."""
        peer_list = "|".join([f"{peer_id}:{host}:{port}" for peer_id, (host, port) in self.peers.items()])
        client_socket.sendall(peer_list.encode())


if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()
    input("Press Enter to stop the tracker.\n")