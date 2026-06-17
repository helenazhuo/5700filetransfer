"""Generates a report, with helper functions."""
import subprocess
from sys import platform
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from RFT_UDPServer import RFT_UDPServer

def format_filesize(fs: int):
    """Formats a files in bytes to a human-readable string.

    Args:
        fs (int): File size as an int.

    Returns:
        str: Formatted file size string (e.g. '10.5 MB').
    """
    if fs < 1024:
        return f"{fs} B"
    elif fs < 1024 ** 2:
        return f"{fs / 1024:.1f} KB"
    elif fs < 1024 ** 3:
        return f"{fs / 1024 ** 2:.1f} MB"
    else:
        return f"{fs / 1024 ** 3:.1f} GB"

def format_duration(seconds: float):
    """Formats a duration in seconds to hh:mm:ss.

    Args:
        seconds (float): Duration in seconds.

    Returns:
        str: Formatted duration string (e.g. '01:30:45').
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"

def compute_md5(filepath: str):
    """Computes the MD5 hash of a file using the OS command line tool.

    Args:
        filepath (str): Path to the file.

    Returns:
        str: Hex string of the MD5 hash.
    """
    if platform.startswith("linux"):
        result = subprocess.run(['md5sum', filepath], capture_output=True, text=True)
        return result.stdout.split()[0]
    elif platform == 'darwin': # MacOS
        result = subprocess.run(['md5', filepath], capture_output=True, text=True)
        return result.stdout.split()[0]
    elif platform == "win32":
        result = subprocess.run(['certutil', '-hashfile', filepath, 'MD5'], capture_output=True, text=True)
        return result.stdout.split('\n')[1].strip()

def generate_report(s: 'RFT_UDPServer', md5_client: str, packets_received_cli: int):
    """Generates a transfer report file for a completed file transfer.

    Writes transfer statistics to a text file named after the server ID and filename.

    Args:
        s (RFT_UDPServer):          The server instance containing transfer statistics.
        md5_client (str):           MD5 hash of the file received by the client.
        packets_received_cli (int): Number of packets received by the client.
    """
    file = f'server{s.server_id}_{s.fn}'
    with open(file, 'w') as f:
        f.write(
            f"Name of the transferred file: {s.fn}\n"
            f"Size of the transferred file: {format_filesize(s.fs)}\n"
            f"Packet loss percentage (0%, 2%, or 4%): {s.loss_pct}%\n"
            f"Number of packets sent from server: {s.packets_sent}\n"
            f"Number of retransmitted packets from server: {s.packets_retransmitted}\n"
            f"Number of packets received by client: {packets_received_cli}\n"
            f"Time duration of file transfer (hh:mm:ss): {s.duration}\n"
            f"MD5 hash of original file to transfer: {s.md5_original}\n"
            f"MD5 hash of received file after transfer: {md5_client}\n"
        )

def print_results(loss_pct: int, md5_original: str, duration: str, md5_client: str):
    """Prints a summary of the file transfer results.

    Args:
        loss_pct (int):       Packet loss percentage (0, 2, or 4).
        md5_original (str):   MD5 hash of the original file.
        duration (str):       Transfer duration as hh:mm:ss.
        md5_client (str):     MD5 hash of the received file.
    """
    success = "successful" if md5_original == md5_client else "failed"
    print(
        "---------------------------------------------------------\n"
        f"MD5 hash of original file:    {md5_original}\n"
        f"MD5 hash of received file:    {md5_client}\n"
        f"File transfer at {loss_pct}%: {success}\n"
        f"Time to transfer (hh:mm:ss):  {duration}\n"
        "---------------------------------------------------------\n"
    )