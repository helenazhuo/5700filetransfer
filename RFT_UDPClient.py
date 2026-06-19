import socket as sock
from RFT_UDPPacket import *
import threading
import time
import os
from RFT_report import *

BUFFER_SIZE = 65535
ACK_INTERVAL = 0.01   # seconds between ACK checks
ACK_THRESHOLD = 100   # only send a cumulative ACK after advancing this many chunks
TIMEOUT = 1.0         # socket recv timeout


class RFT_UDPClient:
    """Requests a file over UDP and receives it using cumulative ACKs.

    Receives file chunks, buffers out-of-order packets, writes them in order,
    and periodically sends a cumulative ACK for the highest contiguous chunk.
    """

    def __init__(self, client_id: int, src_port: int, server_ip: str, server_port: int):
        """Initializes the UDP client.

        Args:
            client_id (int):   Unique identifier for this client instance.
            src_port (int):    Local source port to bind to.
            server_ip (str):   IP address of the server.
            server_port (int): Port number of the server.
        """
        self.client_id = client_id
        self.save_path = None
        # Addressing
        self.src_ip = sock.gethostbyname(sock.gethostname())
        self.src_port = src_port
        self.server_ip = server_ip
        self.server_port = server_port
        # Socket
        self.socket = sock.socket(sock.AF_INET, sock.SOCK_RAW, sock.IPPROTO_UDP)
        self.socket.setsockopt(sock.IPPROTO_IP, sock.IP_HDRINCL, 1)
        self.socket.setsockopt(sock.SOL_SOCKET, sock.SO_RCVBUF, 4 * 1024 * 1024)
        self.socket.bind((self.src_ip, self.src_port))
        self.socket.settimeout(TIMEOUT)
        # State
        self.seq_lock = threading.Lock()
        self.expected_seq = 0     # next contiguous chunk needed
        self.packets_received = 0

    def request_file(self, fn: str):
        """Requests a file and runs the receive + ACK threads until complete.

        Args:
            fn (str): The filename to request.
        """
        self.expected_seq = 0
        self.packets_received = 0

        # Send the request
        payload = f'REQ {fn}'.encode()
        req_packet = build_packet(self.src_ip, self.server_ip,
                                  self.src_port, self.server_port, payload)
        self.socket.sendto(req_packet, (self.server_ip, self.server_port))
        print(f'[CLIENT] Requesting {fn} from {self.server_ip}:{self.server_port}')

        # Prepare save location. fn already includes the test_samples/ prefix,
        # so join only with the saved_files root.
        self.save_path = os.path.join('saved_files', fn)
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        # Run receive and ACK threads
        self.stop_ack = threading.Event()
        recv_t = threading.Thread(target=self.receive_file)
        ack_t = threading.Thread(target=self.ack_monitor)
        recv_t.start()
        ack_t.start()
        recv_t.join()
        ack_t.join()

        # File is closed and flushed by now — send DONE with the MD5
        self.send_done()

    def receive_file(self):
        """Receives chunks, buffers out-of-order ones, writes in order until FIN."""
        received = {}            # seq -> chunk, buffer for out-of-order packets
        with open(self.save_path, 'wb') as f:
            while True:
                try:
                    data, _ = self.socket.recvfrom(BUFFER_SIZE)
                except KeyboardInterrupt:
                    print('\n[CLIENT] Stopping reception.')
                    break
                except sock.timeout:
                    continue
                result = parse_packet(data)
                if result is None:
                    continue
                ip_fields, udp_fields, payload = result
                if udp_fields['src_port'] != self.server_port:
                    continue
                if len(payload) < 5:
                    continue

                self.packets_received += 1
                if self.packets_received % 1000 == 0:
                    print(f'[CLIENT] Received {self.packets_received} packets')

                seq = int.from_bytes(payload[:4], 'big')
                fin = payload[4]
                chunk = payload[5:]

                # FIN: complete only if all chunks up to seq are written
                if fin == 1:
                    with self.seq_lock:
                        done = (self.expected_seq == seq)
                    if done:
                        print(f'[CLIENT] FIN received, all {seq} chunks written')
                        self.stop_ack.set()
                        # final ACK so server can finish
                        self.send_ack(self.expected_seq - 1)
                        break
                    else:
                        # FIN arrived early; keep waiting for missing chunks
                        continue

                # Duplicate or already-written chunk
                if seq < self.expected_seq or seq in received:
                    continue
                received[seq] = chunk

                # Collect contiguous chunks under the lock, write outside it
                with self.seq_lock:
                    to_write = []
                    while self.expected_seq in received:
                        to_write.append(received.pop(self.expected_seq))
                        self.expected_seq += 1
                for c in to_write:
                    f.write(c)

    def ack_monitor(self):
        """Sends a cumulative ACK once the client has advanced ACK_THRESHOLD chunks.

        A time-based fallback still fires the ACK if progress stalls below the
        threshold (e.g. the final partial window), so the server never waits forever.
        """
        last_acked = -1
        stalled_checks = 0
        while not self.stop_ack.is_set():
            with self.seq_lock:
                current = self.expected_seq - 1
            advanced = current - last_acked
            if advanced >= ACK_THRESHOLD:
                # Enough new chunks accumulated — send the cumulative ACK
                self.send_ack(current)
                last_acked = current
                stalled_checks = 0
            elif advanced > 0:
                # Below threshold but still making progress; ACK if it stalls here
                stalled_checks += 1
                if stalled_checks >= 5:   # ~5 * ACK_INTERVAL of no further progress
                    self.send_ack(current)
                    last_acked = current
                    stalled_checks = 0
            time.sleep(ACK_INTERVAL)

    def send_ack(self, seq_num: int):
        """Sends a cumulative ACK for the given sequence number."""
        if seq_num < 0:
            return
        payload = f'ACK {seq_num}'.encode()
        packet = build_packet(self.src_ip, self.server_ip,
                              self.src_port, self.server_port, payload)
        self.socket.sendto(packet, (self.server_ip, self.server_port))

    def send_done(self):
        """Sends the DONE message with the received file's MD5 and packet count."""
        md5_client = compute_md5(self.save_path)
        payload = f'DONE {md5_client} {self.packets_received}'.encode()
        packet = build_packet(self.src_ip, self.server_ip,
                              self.src_port, self.server_port, payload)
        # Send a few times in case of loss
        for _ in range(5):
            self.socket.sendto(packet, (self.server_ip, self.server_port))
            time.sleep(0.05)
        print(f'[CLIENT] DONE sent, md5={md5_client}')

    def close(self):
        """Closes the client socket."""
        self.socket.close()