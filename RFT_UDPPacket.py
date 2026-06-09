import struct
import socket

class RFT_UDPPacket:
    '''Defines the message format for a UDP packet.'''
    def checksum(data):
        data = data << 16
        return
    
    def build_IP_header(src_ip, dest_ip, data_length, id):
        ver = 4
        IHL = 5 # Gives 20 bytes.
        dscp = 0 # Default priority.
        length = 20 + 8 + data_length
        identification = id
        fragment_offset = 0
        ttl = 64
        protocol = socket.IPPROTO_UDP
        header_checksum = 0 # Placeholder
        src = socket.inet_aton(src_ip)
        dst = socket.inet_aton(dest_ip)
        # Pack for checksum.
        IP_header = struct.pack('!BBHHHBBH4s4s', ver, IHL, dscp, length, identification,
                                fragment_offset, ttl, protocol, header_checksum, src, dst)
        # header_checksum = checksum(header)
        # Repack w checksum included.
        IP_header = struct.pack('!BBHHHBBH4s4s', ver, IHL, dscp, length, identification,
                                fragment_offset, ttl, protocol, header_checksum, src, dst)
        return IP_header
    
    def build_UDP_header():
        src_port = 0
        dest_port = 0
        len = 0
        checksum = 0
        data = []
        return
    
    def build_packet():
        IP_header = build_IP_header()
        UDP_header = build_UDP_header()
        data = []
        return IP_header + UDP_header + data
    
    def parse_packet():
        return