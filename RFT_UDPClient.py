class RFT_UDPClient:
     """
     Takes a filename as input to send to a UDP web server to request a download of that file.
     Uses SOCK_RAW as the type of socket.

    Attributes:
        fn (str): The filename.
    """