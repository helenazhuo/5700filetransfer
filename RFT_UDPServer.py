class RFT_UDPServer:
     """
     Given a filename, this server produces a text output file that reports the results of the downloaded file.
     Error control mechanisms included: Checksum, Sequence Numbers, Cumulative Ack #s, Retransmission due to timeout.

    Attributes:
        fn (str): The filename.
    """