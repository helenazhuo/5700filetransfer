import sys
import RFT_UDPClient, RFT_UDPServer, RFT_UDPPacket
fileSizes = ['10mb', '100mb', '500mb', '800mb', '1gb']

# Currently does not check fileSize str. 
def generateTestFileName(fileSize) -> str:
    return 'test_' + {fileSize} + '_file'

def main() -> int:
    choice = None
    while choice != 'c' and choice != 's':
        print("Enter c for client, s for server:")
        choice = input()
        if choice == 'c':
            for size in fileSizes:
                fn = generateTestFileName(size)
                # TODO: implement runClient() in client class -> client = RFT_UDPClient(fn)
                # runClient()
        elif choice == 's':
            # TODO: implement runServer in cerver class
            # runServer()
            print('placeholder') # remove later
        
if __name__ == '__main__':
    sys.exit(main())