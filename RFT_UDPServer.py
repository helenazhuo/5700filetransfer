import socket as sock
import threading
import os
from RFT_UDPPacket import *
from RFT_report import *
import time

CHUNK_SIZE = 1400          
DATA_SIZE = CHUNK_SIZE - 5 # actual file bytes per chunk (4 seq num + 1 fin)
BUFFER_SIZE = 65535
TIMEOUT = 0.5 # seconds to wait for window ACK before resending
WINDOW = 1024 # packets per window
SEND_DELAY = 0.0001 # delay between packets within a window


class RFT_UDPServer:
    """Serves a file over UDP using a sliding window.

    The server sends a specified window amount of packets, then blocks until the client's cumulative ACK advances the window base. Timeout causes the current window to be resent. A client DONE message ends the transfer.
    """

    def __init__(self, server_id, client_ip, client_port):
        """Initializes the UDP server.

        Args:
            server_id (int):   This instance's ID
            client_ip (str):   Client IP address
            client_port (int): Client port number
        """
        # Server & report stats
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
        self.src_port = 12000
        self.dest_ip = client_ip
        self.dest_port = client_port
        # Socket
        self.socket = sock.socket(sock.AF_INET, sock.SOCK_RAW, sock.IPPROTO_UDP)
        self.socket.setsockopt(sock.IPPROTO_IP, sock.IP_HDRINCL, 1)
        self.socket.bind((self.src_ip, self.src_port))
        self.socket.settimeout(TIMEOUT)
        # Transfer state
        self.base = 0            # lowest sequence number to start from
        self.total_chunks = 0    # total data chunks in the file
        self.latest_packet = 0   #latest packet sent
        self.fin_sent = False    
        self.done_received = False  # client's done msg
        self.ack_lock = threading.Lock()

    def start_server(self, mode_selection, loss_pct_selection):
        """Sets server options and starts the listen loop."""
        print(f'Server started @ IP address {self.src_ip}')
        print(f'Waiting for connection from {self.dest_ip}:{self.dest_port}')
        self.mode = mode_selection
        self.loss_pct = loss_pct_selection
        self.stop_listen = threading.Event()
        self.listen()

    def close_server(self):
        """Closes the server socket."""
        self.socket.close()

    def listen(self):
        """Listens for an incoming REQ, then serves the file. Waits for DONE to finish."""
        print(f'[SERVER] Listening on port {self.src_port}')
        while not self.stop_listen.is_set():
            try:
                data, addr = self.socket.recvfrom(BUFFER_SIZE)
            except KeyboardInterrupt:
                print('\n[SERVER] Stopping listen.')
                break
            except sock.timeout:
                # If the file was fully sent but DONE hasn't arrived,
                # the FIN may have been lost — resend it.
                if self.fin_sent and not self.done_received:
                    self.send_fin()
                continue
            except Exception as e:
                print(f'[SERVER] recvfrom error: {e}')
                continue

            result = parse_packet(data)
            if result is None:
                continue
            ip_fields, udp_fields, payload = result
            if udp_fields['dest_port'] != self.src_port:
                continue

            if payload.startswith(b'REQ '):
                self.dest_ip = ip_fields['src_ip']
                self.dest_port = udp_fields['src_port']
                self.handle_req(payload)
            elif payload.startswith(b'DONE '):
                self.handle_done(payload)

    def handle_req(self, payload):
        """Parses a file request and serves the file."""
        self.done_received = False  # fresh transfer; allow its DONE to be processed
        self.fn = payload.split(b' ', 1)[1].decode()
        print(f'[SERVER] Received request for: {self.fn}')
        self.send_file()

    def handle_done(self, payload):
        """Handles the client's DONE message and generates the report.

        Ignores duplicate DONE messages (the client sends several for reliability)
        so the report is only generated once, before state is reset.
        """
        if self.done_received:
            return  # already handled; ignore duplicate DONE
        self.done_received = True
        _, md5_client, packets_received_cli = payload.decode().split(' ')
        print(f'[SERVER] DONE received from client')
        if self.mode == 't':
            self.print_txt_report(md5_client, packets_received_cli)
        self.reset_server()

    def receive_ack(self):
        """Reads ACKs from the socket and advances base. Runs as a thread during send.

        Returns silently on timeout so the sender can resend the window.
        """
        while True:
            try:
                data, addr = self.socket.recvfrom(BUFFER_SIZE)
            except sock.timeout:
                return  # no ACK arrived in this window; sender will resend
            except Exception:
                continue
            result = parse_packet(data)
            if result is None:
                continue
            _, udp_fields, payload = result
            if udp_fields['dest_port'] != self.src_port:
                continue
            if payload.startswith(b'ACK '):
                acked = int(payload.split(b' ', 1)[1])
                with self.ack_lock:
                    if acked + 1 > self.base:
                        self.base = acked + 1  # cumulative ACK advances base
                # Stop reading ACKs once the whole file is acknowledged
                if self.base >= self.total_chunks:
                    return

    def send_file(self):
        """Sends the file window by window, waiting for cumulative ACKs between windows."""
        self.fs = os.path.getsize(self.fn)
        self.total_chunks = (self.fs + DATA_SIZE - 1) // DATA_SIZE  # ceil division
        print(f'[SERVER] Serving {self.fn} ({format_filesize(self.fs)}), '
              f'{self.total_chunks} chunks')
        self.transfer_start = time.time()

        with open(self.fn, 'rb') as f:
            while self.base < self.total_chunks:
                window_start = self.base
                window_end = min(window_start + WINDOW, self.total_chunks)

                # Send every packet in the current window
                for seq in range(window_start, window_end):
                    f.seek(seq * DATA_SIZE)
                    data = f.read(DATA_SIZE)
                    chunk = seq.to_bytes(4, 'big') + bytes([0]) + data
                    packet = build_packet(self.src_ip, self.dest_ip,
                                          self.src_port, self.dest_port,
                                          chunk, self.latest_packet)
                    self.latest_packet += 1
                    self.socket.sendto(packet, (self.dest_ip, self.dest_port))
                    self.packets_sent += 1
                    time.sleep(SEND_DELAY)

                print(f'[SERVER] Sent window [{window_start}, {window_end}), '
                      f'waiting for ACK. base={self.base}')

                # Wait for ACKs to advance base; returns on timeout
                prev_base = self.base
                self.receive_ack()

                # If base didn't advance, the window (or its ACKs) were lost — resend
                if self.base == prev_base:
                    self.packets_retransmitted += (window_end - window_start)
                    print(f'[SERVER] No progress (base={self.base}), resending window')

        # All chunks acknowledged — send FIN until the client confirms with DONE
        self.send_fin()

    def send_fin(self):
        """Sends the FIN packet signaling end of file."""
        fin_payload = self.total_chunks.to_bytes(4, 'big') + bytes([1])
        packet = build_packet(self.src_ip, self.dest_ip,
                              self.src_port, self.dest_port,
                              fin_payload, self.latest_packet)
        self.latest_packet += 1
        self.socket.sendto(packet, (self.dest_ip, self.dest_port))
        self.fin_sent = True
        self.transfer_end = time.time()
        print(f'[SERVER] FIN sent — {self.packets_sent} sent, '
              f'{self.packets_retransmitted} retransmitted')

    def reset_server(self):
        """Resets transfer state for the next request.

        done_received is intentionally NOT reset here — it is cleared in
        handle_req when a new request arrives, so duplicate DONE messages from
        the just-finished transfer continue to be ignored.
        """
        self.base = 0
        self.total_chunks = 0
        self.latest_packet = 0
        self.fin_sent = False
        self.fn = None
        self.fs = 0
        print(f'[SERVER] Ready for next request')

    def print_txt_report(self, md5_client, packets_received_cli):
        """Generates and prints the transfer report."""
        if self.fn is None:
            return  # state already reset; nothing to report
        print(f'[SERVER] Generating report...')
        os.makedirs('reports', exist_ok=True)
        self.md5_original = compute_md5(self.fn)
        self.duration = format_duration(self.transfer_end - self.transfer_start)
        generate_report(self, md5_client, packets_received_cli)
        print_results(self.loss_pct, self.md5_original, self.duration, md5_client)