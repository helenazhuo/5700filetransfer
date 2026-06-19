import sys
from RFT_UDPClient import RFT_UDPClient
from RFT_UDPServer import RFT_UDPServer
file_sizes = ['10mb', '100mb', '500mb', '800mb', '1gb']
# Testing
SERVER_IP = '172.31.35.245'
CLIENT_IP = '172.31.44.54'
SERVER_PORT = 12000
CLIENT_PORT = 12001

def generate_fn(file_size) -> str:
    """Generates a test filename for a given file size string.

    Args:
        file_size (str): File size label (e.g. '10mb', '1gb').

    Returns:
        str: Formatted test filename (e.g. 'test_10mb_file').
    """
    return f'test_samples/test_{file_size}_file'

def prompt_for_dest_IP() -> tuple:
    """Prompts the user to enter a destination IP address.

    Returns:
        dest_ip as str.
    """
    dest_ip = input("Enter destination IP: ")
    return dest_ip

def prompt_for_client() -> tuple:
    """Prompts the user to enter a client IP address and port number for the server.

    Returns:
        tuple: (client_ip, client_port) as (str, int).
    """
    client_ip = input("Enter client IP: ")
    client_port = int(input("Enter client port: "))
    return (client_ip, client_port)

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
    loss_pct = -1
    # Prompt for regular or testing setup
    while mode != 'r' and mode != 't':
        mode = input("Enter 'r' for regular mode, or 't' for testing: ").strip()
        
    # Prompt for cli or server
    while choice != 'c' and choice != 's':
        choice = input("Enter c for client, or s for server: ").strip()
        if choice == 's':
            # Prompt for loss percentage to apply
            if mode == 't':
                while loss_pct not in [0, 2, 4]:
                    loss_pct = int(input("Enter loss % to apply (0, 2, or 4): "))
            servers_num += 1
            if mode == 't':
                client_ip = CLIENT_IP
                client_port = CLIENT_PORT
            else:
                client_ip, client_port = prompt_for_client()
            server = RFT_UDPServer(servers_num, client_ip, client_port)
            server.start_server(mode, loss_pct)
            server.close_server()
        elif choice == 'c':
            clients_num += 1
            if mode != 't':
                (dest_ip) = prompt_for_dest_IP()
            elif mode == 't':
                dest_ip = SERVER_IP
            client = RFT_UDPClient(clients_num, CLIENT_PORT, dest_ip, SERVER_PORT)
            print(f'Client started on IP {client.src_ip}, Port {client.src_port}')
            if mode == 'r':
                fn = input("Enter requested file: ")
                print(f'Requesting: {fn}')
                client.request_file(fn)
            elif mode == 't':
                for size in file_sizes:
                    fn = generate_fn(size)
                    print(f'Requesting: {fn}')
                    client.request_file(fn)
            client.close()
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nExiting program.')
        sys.exit(0)