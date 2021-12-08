import socket
import sys
import os
import watchdog
import time
import string
import random

LIMITED_SIZE = 1024

def main():

    updates_map = dict()
    folder_names_map = dict()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(('', int(sys.argv[1])))
    except Exception:
        print("invalid input")
        sys.exit()

    server.listen(15)
    while True:
        # 1.Connect to the client
        client_socket, client_address = server.accept()
        print('Connection from: ', client_address)

        newClient = 0
        computerIdentifier = client_socket.recv(128).decode()
        if computerIdentifier != '0' * 128:
            newClient = 2
        if newClient != 2:
            computerIdentifier = ''
            for i in range(128):
                computerIdentifier = computerIdentifier + random.choice(string.ascii_letters + string.digits)
            client_socket.send(computerIdentifier.encode())
            identifier = client_socket.recv(128).decode()
            if identifier == '0':
                print('working')
                newClient = 1
            # 2.create new identifier and send to the client
            if newClient == 1:
                identifier = ''
                for i in range(128):
                    identifier = identifier + random.choice(string.ascii_letters + string.digits)
            # add to the updates map pair of {identifier:{computer identifier:[empty list for the future changes]}}
            client_socket.send(identifier.encode())
            # todo
            updates_map[identifier] = {computerIdentifier:[]}
            print(identifier)

            # 3.get the directory
            if newClient == 1:
                # os.makedirs(identifier, exist_ok=True)
                msg_len = client_socket.recv(12).decode()
                directory_name = client_socket.recv(int(msg_len)).decode()
                folder_names_map[identifier] = directory_name
                directory_path = os.path.join(identifier, directory_name)
                # os.makedirs(os.path.dirname(path), exist_ok=True)
                while True:
                    msg_len = client_socket.recv(12).decode()
                    if msg_len == 'finish_all!!':
                        break
                    while msg_len != 'finish_dires':
                        dirrelpath = client_socket.recv(int(msg_len)).decode()
                        dirname = os.path.join(directory_path, dirrelpath)
                        os.makedirs(dirname)
                        msg_len = client_socket.recv(12).decode()
                    while True:
                        msg_len = client_socket.recv(12).decode() # recive relpath length
                        if msg_len == 'finish_files':
                            break
                        relpath = client_socket.recv(int(msg_len)).decode() # recive relpath
                        dst_path = os.path.join(directory_path, relpath)
                        length = int(client_socket.recv(12).decode())  # recive file length
                        # Read the data in chunks so it can handle large files.
                        with open(dst_path, 'wb') as f:
                            while length:
                                msg_len = min(length, LIMITED_SIZE)
                                data = client_socket.recv(msg_len)
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
                msg_len = str(len(folder_names_map[identifier])).zfill(12)
                client_socket.send(msg_len.encode())
                client_socket.send(folder_names_map[identifier].encode())
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
                                data = f.read(LIMITED_SIZE)
                                if not data: break
                                client_socket.sendall(data)
                print('Done.')
            # print(updates_map)
            client_socket.close()

        else:
            print('old known client connected!!!')
            events_list_length = client_socket.recv(12).decode()  # recive length of events list
            if events_list_length == '000000000000':
                events_list_length = '0'
            for i in range(int(events_list_length)):
                msg_len = client_socket.recv(12).decode() # recive event_type length
                if msg_len == '000000000000':
                    msg_len = '0'
                event_type = client_socket.recv(int(msg_len)).decode() # recive event_type

                # case of deleted event
                if event_type == 'deleted':
                    msg_len = client_socket.recv(12).decode() # recive relpath length
                    relpath = client_socket.recv(int(msg_len)).decode() # recive relpath
                    dst_path = os.path.join(directory_path, relpath)
                    is_directory = client_socket.recv(1).decode() # recive is_directory
                    if is_directory == '1':
                        for root, dirs, files in os.walk(dst_path, topdown=False):
                            for name in files:
                                os.remove(os.path.join(root, name))
                            for name in dirs:
                                os.rmdir(os.path.join(root, name))
                        os.rmdir(dst_path)
                    else:
                        os.remove(dst_path)

                # case of created event
                if event_type == 'created':
                    msg_len = client_socket.recv(12).decode() # recive relpath length
                    relpath = client_socket.recv(int(msg_len)).decode() # recive relpath
                    dst_path = os.path.join(directory_path, relpath)
                    is_directory = client_socket.recv(1).decode() # recive is_directory
                    if is_directory == '1':
                        os.makedirs(dst_path)
                    else:
                        length = int(client_socket.recv(12).decode())  # recive file length
                        # Read the data in chunks so it can handle large files.
                        with open(dst_path, 'w') as f:
                            while length:
                                msg_len = min(length, LIMITED_SIZE)
                                data = client_socket.recv(msg_len).decode()
                                if not data: break
                                f.write(data)
                                length -= len(data)
                            else:  # only runs if while doesn't break and length==0
                                print('Complete')
                                continue
                                # socket was closed early.
                        print('Incomplete')
                        break




            client_socket.close()

if __name__ == "__main__":
    main()