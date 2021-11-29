import socket
import sys
import os
import watchdog
import time
import string
import random

CHUNKSIZE = 1_000_000

def main():

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(('', int(sys.argv[1])))
    except Exception:
        print("invalid input")
        sys.exit()

    server.listen()
    while True:
        # 1.Connect to the client
        client_socket, client_address = server.accept()
        print('Connection from: ', client_address)

        newClient = 0
        computerIdentifier = client_socket.recv(128).decode()
        if computerIdentifier != '0' * 128:
            newClient = 2
        if newClient != 2:
            identifier = client_socket.recv(128).decode()
            if identifier == '0':
                print('working')
                newClient = 1
            # 2.create new identifier and send to the client
            if newClient == 1:
                identifier = random.choice(string.ascii_letters + string.digits)
                for i in range(127):
                    identifier = identifier + random.choice(string.ascii_letters + string.digits)
            client_socket.send(identifier.encode())
            print(identifier)

            # 3.get the directory
            if newClient == 1:
                os.makedirs(identifier, exist_ok=True)
                with client_socket, client_socket.makefile('rb') as clientfile:
                    while True:
                        raw = clientfile.readline()
                        if not raw: break  # no more files, server closed connection.

                        filename = raw.strip().decode()
                        length = int(clientfile.readline())
                        print(f'Downloading {filename}...\n  Expecting {length:,} bytes...', end='', flush=True)

                        path = os.path.join(identifier, filename)
                        os.makedirs(os.path.dirname(path), exist_ok=True)

                        # Read the data in chunks so it can handle large files.
                        with open(path, 'wb') as f:
                            while length:
                                chunk = min(length, CHUNKSIZE)
                                data = clientfile.read(chunk)
                                if not data: break
                                f.write(data)
                                length -= len(data)
                            else:  # only runs if while doesn't break and length==0
                                print('Complete')
                                continue
                                # socket was closed early.
                        print('Incomplete')
                        break
            else:
                directory = identifier
                for path, dirs, files in os.walk(directory):
                    for file in files:
                        filename = os.path.join(path, file)
                        relpath = os.path.relpath(filename, directory)
                        filesize = os.path.getsize(filename)

                        print(f'Sending {relpath}')

                        with open(filename, 'rb') as f:
                            client_socket.sendall(relpath.encode() + b'\n')
                            client_socket.sendall(str(filesize).encode() + b'\n')

                            # Send the file in chunks so large files can be handled.
                            while True:
                                data = f.read(CHUNKSIZE)
                                if not data: break
                                client_socket.sendall(data)
                print('Done.')

            client_socket.close()

        else:
            print('old known client connected!!!')
            client_socket.close()

if __name__ == "__main__":
    main()