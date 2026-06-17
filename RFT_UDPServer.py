import socket as sock
import threading
import os
from RFT_UDPPacket import *
from RFT_report import *
import time

CHUNK_SIZE = 1400 # bytes

class RFT_UDPServer:
    """Serves a file and outputs a text file that reports its results.

    Handles listening for filename requests, reading the file, sending file chunks with seq nums, and retransmission on timeout. 
    """

    def __init__(self, server_id):
        """Initializes the UDP client.

        Args:
            server_id (int):    Unique identifier for this server instance.
        """
        # Server & Report Stats
        self.server_id = server_id
        self.mode = None
        self.loss_pct = 0
        self.fn = None
        self.fs = 0
        self.md5_original = None
        self.duration = None
        self.packets_sent = 0
        self.packets_retransmitted = 0
        self.transfer_start = None
        self.transfer_end = None
        # Addressing
        self.src_ip = sock.gethostbyname(sock.gethostname())
        self.src_port = 0  # 0 -> OS assigns an available port
        self.dest_ip = None
        self.dest_port = None
        # Socket
        self.socket = sock.socket(sock.AF_INET, sock.SOCK_RAW, sock.IPProto_UDP)
        self.socket.bind((self.src_ip, self.src_port))
        self.timeout = 1.0
        self.socket.settimeout(self.timeout)
        # Counters
        self.seq_num = 0
        self.latest_acked = 0 # Last ack received
        self.dupe_acks = 0
        self.latest_packet = 0 # Last packet sent
        self.fin_sent = False # Final packet sent

    def start_server(self, mode_selection, loss_pct_selection):
        """Sets server options and starts server by running multiple threads."""
        # Set server options
        self.mode = mode_selection
        self.loss_pct = loss_pct_selection
        # Report stat
        self.transfer_start = time.time()
        # On start
        self.stop_listen = threading.Event()
        listen_t = threading.Thread(target=self.listen, args=())
        listen_t.start()
        listen_t.join()

    def close_server(self):
        """Dedicated server close."""
        self.socket.close()
        
    def listen(self)->str:
        """Listens for incoming packets and handles according to message."""
        while not self.stop_listen.is_set():
            try:
                data, (self.dest_ip, self.dest_port) = self.socket.recvfrom(65535)
            except sock.timeout:
                self.handle_timeout()
                continue
            result = parse_packet(data)
            if result is None: # checksum failed, discard
                continue
            _, _, payload = result # discard ip_fields and udp_fields
            if payload.startswith(b'REQ '):
                self.handle_req(payload)
            elif payload.startswith(b'ACK '):
                self.handle_ack(payload)
            elif payload.startswith(b'DONE '):
                self.handle_done(payload)

    def handle_done(self, payload):
        """Handles a DONE message indicating final report can be generated."""
        _, md5_client, packets_received_cli = payload.decode().split(' ')
        if self.mode == 't': self.print_txt_report(md5_client, packets_received_cli)

    def handle_req(self, payload):
        """Handles a file request by dedicating a worker thread."""
        self.fn = payload.split(b' ', 1)[1].decode()              
        handler_t = threading.Thread(target=self.handle_client, args=())
        handler_t.start()

    def handle_ack(self, payload):
        """Handles an acknowledgement."""
        acked = int(payload.split(b' ', 1)[1])   
        if acked == self.latest_acked:
            # Handle duplicate ack
            self.dupe_acks += 1
            # Handle 3 duplicate acks
            if self.dupe_acks == 3:
                self.retransmit()
                self.dupe_acks = 0
        # Updated ack. Ignore outdated acks.
        elif acked > self.latest_acked:
            self.latest_acked = acked
            # Handle the last ack sent after FIN was sent
            if self.fin_sent == True:
                self.transfer_end = time.time()
                self.stop_listen.set()
                
    def handle_timeout(self):
        """Handles a timeout and updates the duration of the timeout."""
        self.timeout *= 2
        self.socket.settimeout(self.timeout)
        if self.fn is not None:
            self.retransmit()
        return
    
    def handle_client(self):
        """Dedicated client handler for a worker thread."""
        self.fs = os.path.getsize(self.fn)
        self.send_file()

    def send_file(self, retransmit = False):
        """Sends a file and checks if it is a retransmission."""
        read_from = self.latest_acked * (CHUNK_SIZE - 5) if retransmit else 0

        with open(self.fn, 'rb') as f:
            f.seek(read_from) # move to this byte offset
            while True:
                fin = 0
                data = f.read(CHUNK_SIZE - 5)
                if not data:
                    self.send_fin()
                    break
                chunk = self.seq_num.to_bytes(4,'big') + bytes([fin]) + data
                packet = build_packet(self.src_ip, self.dest_ip, self.src_port, self.dest_port, chunk, self.latest_packet)
                self.latest_packet += 1
                self.socket.sendto(packet, (self.dest_ip, self.dest_port))
                self.seq_num += 1
                # Report stats
                if retransmit == True:
                    self.packets_retransmitted += 1
                else:
                    self.packets_sent += 1
        return

    def send_fin(self):
        """Handles sending FIN message to client."""
        fin = b'\x01'
        fin_payload = self.seq_num.to_bytes(4, 'big') + fin  # Payload = seq num bytes 0 to 3, fin flag, no data
        packet = build_packet(self.src_ip, self.dest_ip, self.src_port, self.dest_port, fin_payload, self.seq_num)
        self.socket.sendto(packet, (self.dest_ip, self.dest_port))
        self.fin_sent = True

    def retransmit(self):
        """Retransmits a file."""
        self.send_file(True)
        return
    
    def print_txt_report(self, md5_client, packets_received_cli):
        """Prints a text report."""
        os.makedirs('reports', exist_ok=True)
        self.md5_original = compute_md5(self.fn)
        duration_unfmt = self.transfer_end - self.transfer_start
        self.duration = format_duration(duration_unfmt)
        generate_report(self, md5_client, packets_received_cli)
        print_results(self.loss_pct, self.md5_original, self.duration, md5_client)
        