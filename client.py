import socket
import sys
import os
import watchdog
import time
import string
import random

LIMITED_SIZE = 100000

def main():
    timeout = int(sys.argv[4])
    computerIdentifier = '0' * 128

    # 1.connect to the server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((sys.argv[1], int(sys.argv[2])))

    # 2.get new identifier if need or send the identifier that get from the input
    server_socket.send(computerIdentifier.encode())
    computerIdentifier = server_socket.recv(128).decode()
    newClient = 0
    if len(sys.argv) == 5:
        newClient = 1
    identifier = '0'
    if len(sys.argv) == 6:
        identifier = sys.argv[5]
    server_socket.send(identifier.encode())
    identifier = server_socket.recv(128).decode()
    print('identifier is: ', identifier)

    # 3.if new client - send directory
    if newClient == 1:
        directory = sys.argv[3]
        head, tail = os.path.split(directory)
        msg_len = str(len(tail)).zfill(12)
        server_socket.send(msg_len.encode())
        server_socket.send(tail.encode())
        for path, dirs, files in os.walk(directory):
            for file in files:
                filename = os.path.join(path, file)
                relpath = os.path.relpath(filename, directory)
                filesize = os.path.getsize(filename)

                print(f'Sending {relpath}')

                with open(filename, 'rb') as f:
                    server_socket.sendall(relpath.encode() + b'\n')
                    server_socket.sendall(str(filesize).encode() + b'\n')

                    # Send the file in chunks so large files can be handled.
                    while True:
                        data = f.read(LIMITED_SIZE)
                        if not data: break
                        server_socket.sendall(data)
        print('Done.')
    # 4.if the client already exist - get directory
    else:
        os.makedirs(identifier, exist_ok=True)
        with server_socket, server_socket.makefile('rb') as clientfile:
            while True:
                raw = clientfile.readline()
                if not raw: break  # no more files, server closed connection.

                filename = raw.strip().decode()
                length = int(clientfile.readline())
                print(f'Downloading {filename}...\n  Expecting {length:,} bytes...', end='', flush=True)

                cwd = os.getcwd()
                path = os.path.join(cwd, filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)

                # Read the data in chunks so it can handle large files.
                with open(path, 'wb') as f:
                    while length:
                        chunk = min(length, LIMITED_SIZE)
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
    server_socket.close()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((sys.argv[1], int(sys.argv[2])))


if __name__ == "__main__":
    main()
