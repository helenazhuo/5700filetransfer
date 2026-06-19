import struct
import socket
'''Defines the message format for a UDP packet.'''

def checksum(data: bytes):
    """Computes the checksum following RFC 791 one's complement algorithm.

    Sums the data as 16-bit words with zero-padding for odd lengths,
    folds carry bits, and returns the one's complement.

    Args:
        data (bytes): Raw bytes to checksum (i.e. IP header or UDP header).

    Returns:
        int: 16-bit checksum value.
    """
    # Accumulate the one's complement sum. For each 2-byte word, shift the first byte into high 8 bits and rest into low 8 bits
    s = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) + (data[i+1] if i+1 < len(data) else 0) # pads an odd-length with zeroes if needed
        s += w
    # Carry folding: extract overflow and retain lower 16 bits. Do until s fits in 16 bits.
    while s >> 16:
        s = (s >> 16) + (s & 0xffff)
    # One's complement: Flip bits of s with NOT and mask to 16 bits.
    return ~s & 0xffff

def build_IP_header(src_ip: str, dest_ip: str, payload_length: int, packet_id: int):
    """Builds a 20-byte IPv4 header.

    Args:
        src_ip (str):      Source IP address (e.g. '192.168.1.1').
        dest_ip (str):     Destination IP address.
        payload_length (int): Length of the payload in bytes.
        packet_id (int):          Packet identification number, incremented per packet.

    Returns:
        bytes: A packed 20-byte IPv4 header with checksum.
    """
    # Fixed constants
    ver = 0b0100 # IPv4
    IHL = 0b0101 # 5 32-bit words = 5 * 4 = 20-byte header
    ver_IHL = (ver << 4) | IHL # Combines ver and IHL into 1 byte
    dscp_ecn = 0 # Default priority, 1 byte
    length = 20 + 8 + payload_length # IP header + UDP header + payload
    packet_id = packet_id % 65535 # Wrap to 16-bit
    fragment_offset = 0
    flags = 0b010 # Don't fragment
    fragment_flags = (flags << 13) | fragment_offset
    ttl = 64
    protocol = socket.IPPROTO_UDP

    # Variables
    src = socket.inet_aton(src_ip)
    dst = socket.inet_aton(dest_ip)

    # Pack with placeholder checksum, then repack with computed checksum.
    # Total: 1+1+2+2+2+1+1+2+4+4 = 20 bytes.
    header_checksum = 0
    IP_header = struct.pack('!BBHHHBBH4s4s',ver_IHL, dscp_ecn, length, packet_id,
                            fragment_flags, ttl, protocol, header_checksum, src, dst)
    header_checksum = checksum(IP_header)
    IP_header = struct.pack('!BBHHHBBH4s4s',ver_IHL, dscp_ecn, length, packet_id,
                            fragment_flags, ttl, protocol, header_checksum, src, dst)                
    return IP_header

def build_UDP_header(src_port: int, dest_port: int, payload: bytes):
    """Builds an 8-byte UDP header.

    Args:
        src_port (int):      Source port number.
        dest_port (int):     Destination port number.
        payload (bytes): Data to be carried in the UDP packet.

    Returns:
        bytes: A packed 8-byte UDP header.
    """
    length = 8 + len(payload) # 8-byte header + payload
    udp_checksum = 0 # No checksum over pseudoheader
    return struct.pack('!HHHH', src_port, dest_port, length, udp_checksum)

def build_packet(src_ip: str, dest_ip: str, src_port: int, dest_port: int, payload: bytes, packet_id=0):
    """Builds a packet from an IP header, UDP header, and payload.
    """
    payload_length = len(payload)
    IP_header = build_IP_header(src_ip, dest_ip, payload_length, packet_id)
    UDP_header = build_UDP_header(src_port, dest_port, payload)
    return IP_header + UDP_header + payload

def parse_packet(data: bytes):
    """Parses a raw packet into its IP header, UDP header, and payload, and verifies its integrity.

    Args:
        data (bytes): Raw bytes received off the socket.

    Returns:
        tuple: (ip_fields, udp_fields, payload) as dictionaries and bytes. None if the packet is corrupted.
    """
    # Fixed sizes
    IP_HEADER_SIZE = 20
    UDP_HEADER_SIZE = 8

    # Unpack IP header
    ip_raw = data[:IP_HEADER_SIZE]
    ver_IHL, dscp_ecn, length, packet_id, fragment_flags, ttl, protocol, ip_checksum, src_ip, dst_ip = \
        struct.unpack('!BBHHHBBH4s4s', ip_raw)
    
    # Filter non-UDP packets before checksum check
    if protocol != socket.IPPROTO_UDP:
        return None

    # Verify integrity of packet. Discard packet and request retransmission if corrupted.
    # IP header checksum field is zeroed out due to OS modification of that field
    ip_raw_for_check = ip_raw[:10] + b'\x00\x00' + ip_raw[12:]
    computed = checksum(ip_raw_for_check)
    if computed != ip_checksum:
        print(f'[PACKET] Error: Checksum mismatch.')
        return None

    # Unpack UDP header
    udp_raw = data[IP_HEADER_SIZE : IP_HEADER_SIZE + UDP_HEADER_SIZE]
    src_port, dest_port, udp_length, udp_checksum = struct.unpack('!HHHH', udp_raw)

    # Everything after both headers is the payload
    payload = data[IP_HEADER_SIZE + UDP_HEADER_SIZE:]

    ip_fields = {
        'ver_IHL': ver_IHL,
        'length': length,
        'packet_id': packet_id,
        'ttl': ttl,
        'protocol': protocol,
        'checksum': ip_checksum,
        'src_ip': socket.inet_ntoa(src_ip),
        'dst_ip': socket.inet_ntoa(dst_ip)
    }

    udp_fields = {
        'src_port': src_port,
        'dest_port': dest_port,
        'length': udp_length,
        'checksum': udp_checksum
    }

    return ip_fields, udp_fields, payload