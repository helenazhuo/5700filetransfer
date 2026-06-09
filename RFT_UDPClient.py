from socket import socket, timeout, AF_INET, SOCK_RAW

class RFT_UDPClient:
    """Requests download of a file from a UDP web server.

    Attributes:
        fn (str): The filename.
    """
     
    def __init__(self, clientID):
        id = clientID
    
    def reqFn(self, fn, serverName, serverPort):
        message = f'REQ {fn}' # TODO: construct msg with RFT_UDPPacket.py
        clientSocket = socket(AF_INET, SOCK_RAW)
        clientSocket.settimeout(1.0)
        self.clientSocket.sendto(message.encode(), (serverName, serverPort))
        try: 
            reply, serverAddress = clientSocket.recvfrom(1024)
            print('Response:', reply)
        except timeout as e:
            f'Error: request timed out.'
        clientSocket.close()