from socket import socket, AF_INET, SOCK_RAW
initIP = ''
initPort = 12000

class RFT_UDPServer:
    """Outputs a text file that reports the results of a downloaded file.

    Attributes:
        fn (str): The filename.
    """

    # Start with one socket
    def __init__(self):
        sockets = [self.addSocket(initIP, initPort)]

    def addSocket(self, IPaddress, portNum)->socket:
        ip = IPaddress
        port = portNum
        serverSocket = socket(AF_INET, SOCK_RAW)
        return serverSocket

    def startServer(self):
        initSocket = self.sockets[0]
        msg, address = initSocket.recvfrom(1024)

        # Response
        response = 'getFile' # TODO: implement. Open new sockets if neccessary
        initSocket.sendto(response, address)
        
    def reportToTxt(self)->bool:
        # TODO: implement
        return True