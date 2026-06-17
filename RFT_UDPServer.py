import socket as sock
import threading
import os
from RFT_UDPPacket import *

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
        # Addressing
        self.src_ip = sock.gethostbyname(sock.gethostname())
        self.src_port = 0  # 0 -> OS assigns an available port
        self.dest_ip = None
        self.dest_port = None
        self.fn = None
        # Socket
        self.socket = socket(sock.AF_INET, sock.SOCK_RAW)
        self.socket.settimeout(1.0)
        # Counters
        self.latest_acked = 0
        self.dupe_acks = 0
        self.latest_packet = None

    def start_server(self):
        self.stop_listen = threading.Event()
        listen_t = threading.Thread(target=self.listen, args=())
        listen_t.start()
        listen_t.join()

    def close_server(self, test_option=None):
        if test_option == 't': self.print_txt_report()
        self.socket.close()
        
    def listen(self)->str:
        while not self.stop_listen.is_set():
            try:
                data, (self.dest_ip, self.dest_port) = self.socket.recvfrom(65535)
            except sock.timeout:
                self.retransmit()
            result = parse_packet(data)
            if result is None: # checksum failed, discard
                continue
            ip_fields, udp_fields, payload = result
            if payload.startswith('REQ '):
                self.fn = payload.split(' ', 1)[1]                 
                handler_t = threading.Thread(target=self.handle_client, args=())
                handler_t.start()
            elif payload.startswith('ACK '):
                acked = payload.split(' ', 1)[1]   
                if acked == self.latest_acked:
                    self.dupe_acks += 1
                    if self.dupe_acks == 3:
                        self.retransmit()
                        self.dupe_acks = 0
                elif acked != self.latest_acked:
                    self.latest_acked = acked
            self.socket.settimeout *= 2            
    
    def handle_client(self):
        self.send_file()

    def send_file(self, read_from = 0):
        with open(self.fn, 'rb') as f:
            while True:
                f.seek(read_from) # move to this byte offset
                fin = 0
                chunk = self.seq_num + fin + f.read(CHUNK_SIZE - 4)
                if not chunk:
                    self.send_fin()
                    break
                packet = build_packet(self.src_ip, self.dest_ip, self.src_port, self.dest_port, chunk, self.latest_packet)
                self.socket.sendto(packet, self.dest_ip)
                self.seq_num += 1
        return

    def send_fin(self):
        fin = 1
        fin_payload = self.seq_num + fin + (CHUNK_SIZE - 4) # Payload = seq num bytes 0 to 3, fin flag, chunk
        packet = build_packet(self.src_ip, self.dest_ip, self.src_port, self.dest_port, fin_payload, self.seq_num)
        self.socket.sendto(packet, self.dest_ip)

    def retransmit(self):
        self.send_file(self, self.latest_acked)
        return
    
    def print_txt_report(self):
        folder = os.path.dirname('reports')
        os.makedirs(folder, exist_ok=True)
        file = f'server{self.server_id}_{self.fn}'
        
        with open(file, 'w') as f:
            f.write(
                f"Name of the transferred file:          {self.fn}\n"
                f"Size of the transferred file:          {self.file_size}\n"
                f"Packet loss percentage:                {self.loss_pct}%\n"
                f"Packets sent from server:              {self.packets_sent}\n"
                f"Retransmitted packets from server:     {self.packets_retransmitted}\n"
                f"Packets received by client:            {self.packets_received}\n"
                f"Transfer duration (hh:mm:ss):          {self.duration}\n"
                f"MD5 hash of original file:             {self.md5_original}\n"
                f"MD5 hash of received file:             {self.md5_received}\n"
            )
