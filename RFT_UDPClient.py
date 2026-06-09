from socket import socket, timeout, AF_INET, SOCK_RAW

class RFT_UDPClient:
    """Requests download of a file from a UDP web server.

    Attributes:
        fn (str): The filename.
    """
     
    def __init__(self, clientID):
        id = clientID
    
    def request_file(self, fn, serverName, serverPort):
        request_msg = f'REQ {fn}' # TODO: construct msg with RFT_UDPPacket.py
        client_socket = socket(AF_INET, SOCK_RAW)
        client_socket.settimeout(1.0)
        self.clientSocket.sendto(request_msg.encode(), (serverName, serverPort))
        try: 
            reply, serverAddress = client_socket.recvfrom(1024)
            print('Response:', reply)
        except timeout as e:
            f'Error: request timed out.'
        client_socket.close()