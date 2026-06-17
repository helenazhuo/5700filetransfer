import sys
from RFT_UDPClient import RFT_UDPClient
from RFT_UDPServer import RFT_UDPServer
file_sizes = ['10mb', '100mb', '500mb', '800mb', '1gb']
# Testing
SERVER_IP = '127.0.0.1'
SERVER_PORT = 12000

def generate_fn(file_size) -> str:
    """Generates a test filename for a given file size string.

    Args:
        file_size (str): File size label (e.g. '10mb', '1gb').

    Returns:
        str: Formatted test filename (e.g. 'test_10mb_file').
    """
    return f'test_{file_size}_file'

def prompt_for_dest() -> tuple:
    """Prompts the user to enter a destination IP address and port number.

    Returns:
        tuple: (dest_ip, dest_port) as (str, int).
    """
    dest_ip = input("Enter destination IP: ")
    dest_port = int(input("Enter destination port: "))
    return (dest_ip, dest_port)

def main() -> int:
    print("RFT Program")
    print("---------------")
    # Tracks cli and server objs
    global clients_num, servers_num
    clients_num = 0
    servers_num = 0
    # Tracks runtime options
    mode = None
    choice = None
    loss_pct = 0
    # Prompt for regular or testing setup
    while mode != 'r' and mode != 't':
        mode = input("Enter 'r' for regular mode, or 't' for testing: ").strip()
        # Prompt for loss percentage to apply
        if mode == 't':
            while loss_pct not in [0, 2, 4]:
                loss_pct = int(input("Enter loss % to apply (0, 2, or 4): "))
    # Prompt for cli or server
    while choice != 'c' and choice != 's':
        choice = input("Enter c for client, or s for server: ").strip()
        if choice == 's':
            servers_num += 1
            server = RFT_UDPServer(servers_num)
            server.start_server(mode, loss_pct)
            server.close_server()
        elif choice == 'c':
            clients_num += 1
            (dest_ip, dest_port) = prompt_for_dest()
            client = RFT_UDPClient(clients_num, dest_ip, dest_port)
            if mode == 'r':
                fn = input("Enter requested file: ")
                print(f'Requesting: {fn}')
                client.request_file(fn, dest_ip, dest_port)
            elif mode == 't':
                for size in file_sizes:
                    fn = generate_fn(size)
                    print(f'Requesting: {fn}')
                    client.request_file(fn, dest_ip, dest_port)
            client.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())