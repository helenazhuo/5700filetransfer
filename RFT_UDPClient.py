import socket as sock
from RFT_UDPPacket import *
import threading
import time
import os
from RFT_report import *

class RFT_UDPClient:
    """Requests download of a file from a UDP web server.
    
    Sends the filename to request, receives file segments, verifies checksums and sends cumulative ACKs.
    """

    def __init__(self, client_id: int, server_ip: str, server_port: int):
        """Initializes the UDP client.

        Args:
            client_id (int):    Unique identifier for this client instance.
            server_ip (str):    IP address of the server.
            server_port (int):  Port number of the server.
        """
        self.client_id = client_id
        self.save_path = None
        # Packet
        self.src_ip = sock.gethostbyname(sock.gethostname())
        self.src_port = 0  # 0 -> OS assigns an available port
        self.server_ip = server_ip
        self.server_port = server_port
        # Sockets
        self.socket = sock.socket(sock.AF_INET, sock.SOCK_RAW, sock.IPPROTO_UDP)
        self.socket.bind((self.src_ip, self.src_port))
        self.socket.settimeout(1.0)
        # Counters & Threading
        self.seq_num_lock = threading.Lock()
        self.expected_seq = 0        # next expected sequence number
        # Report stats
        self.packets_received = 0
    
    def request_file(self, fn: str, dest_ip: str, dest_port: int):
        """Requests a file for a specified server.
        
        Starts a thread for receiving and a thread for sending ACKs.

        Args:
            fn (str): The filename.
            dest_ip (str): Destination IP address.
            dest_port (int): Destination port.
        """
        print(f'[CLIENT] Requesting {fn} from {dest_ip}:{dest_port}')
        # Send request packet
        payload = f'REQ {fn}'.encode()
        req_packet = build_packet(self.src_ip, dest_ip, self.src_port, dest_port, payload)
        self.socket.sendto(req_packet, (dest_ip, dest_port))

        # Create dir for file
        self.save_path = os.path.join('saved_files', f'client_{self.client_id}', fn)
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        # Start threads for receiving file packets and sending acks
        self.stop_ack = threading.Event()
        recv_t = threading.Thread(target=self.receive_file, args=())
        ack_t = threading.Thread(target=self.ack_monitor, args=(dest_ip, dest_port))
        recv_t.start()
        ack_t.start()
        recv_t.join()
        ack_t.join()

    def receive_file(self):
        """Receives file chunks from the server, verifies integrity, and writes/saves file."""
        received = {} # Tracks received chunks, indexed by seq_num.
        with open(self.save_path, 'wb') as f: # open in binary mode
            while True:
                # Receive packet and parse
                try:
                    data, server_address = self.socket.recvfrom(65535)
                except sock.timeout:
                    continue # if no data sent yet, wait
                # If successful, parse
                result = parse_packet(data)
                if result is None:          # checksum failed, discard
                    continue
                # Valid packets: increment count and extract data
                self.packets_received += 1
                if self.packets_received % 100 == 0:
                    print(f'[CLIENT] Received {self.packets_received} packets')
                ip_fields, udp_fields, payload = result

                # Parse sequence number and FIN flag from payload header
                seq_num = int.from_bytes(payload[:4], 'big') # big-endian bytes 0 to 3
                fin = payload[4]
                chunk = payload[5:] if fin != 1 else b'' # If fin then empty chunk expected

                # Discard duplicates, otherwise store in received
                if seq_num in received:
                    continue
                received[seq_num] = chunk

                # Write all chunks consecutively to disk. Out-of-order packets are buffered.
                with self.seq_num_lock:
                    while self.expected_seq in received:
                        f.write(received.pop(self.expected_seq))
                        self.expected_seq += 1
                    write_done = self.expected_seq - 1 == seq_num
                    if fin and write_done:
                        print(f'[CLIENT] File fully received — {self.packets_received} packets total')
                        self.stop_ack.set()
                        dest_ip = ip_fields['src_ip']
                        dest_port = udp_fields['src_port']
                        self.send_ack(self.expected_seq - 1, dest_ip, dest_port) # final ack
                        self.send_fin_report(dest_ip, dest_port) # Final report
                        break   # FIN received and all prior chunks written, file fully received.
    
    def ack_monitor(self, dest_ip: str, dest_port: int):
        """Monitors sequence numbers to send acknowledgements after a specified time interval."""
        ACK_INTERVAL = 0.1
        last_acked = -1
        while not self.stop_ack.is_set():
            with self.seq_num_lock:
                current_seq = self.expected_seq - 1
            if current_seq > last_acked:
                self.send_ack(current_seq, dest_ip, dest_port)
                last_acked = current_seq
            time.sleep(ACK_INTERVAL)

    def send_ack(self, seq_num: int, dest_ip: str, dest_port: int):
        """Sends ACK to specified destination."""
        payload = f'ACK {seq_num}'.encode()
        ack_packet = build_packet(self.src_ip, dest_ip, self.src_port, dest_port, payload)
        self.socket.sendto(ack_packet, (dest_ip, dest_port))

    def send_fin_report(self, dest_ip: str, dest_port: int):
        """Sends final report stats client-side to server with a DONE msg."""
        print(f'[CLIENT] Sending DONE report to server')
        md5_client = compute_md5(self.save_path)
        payload = f'DONE {md5_client} {self.packets_received}'.encode()
        packet = build_packet(self.src_ip, dest_ip, self.src_port, dest_port, payload)
        self.socket.sendto(packet, (dest_ip, dest_port))

    def close(self):
        """Closes the client socket."""
        self.socket.close()