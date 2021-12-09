import socket
import sys
import os
import watchdog
import time
import string
import random

LIMITED_SIZE = 30000

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
        # Connect to the client
        client_socket, client_address = server.accept()
        print('Connection from: ', client_address)

        # set identifier and computeridentifier for this client device
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
            if newClient == 1:
                identifier = ''
                for i in range(128):
                    identifier = identifier + random.choice(string.ascii_letters + string.digits)
                updates_map.update({identifier: dict()})
            # add to the updates map pair of {identifier:{computer identifier:[empty list for the future changes]}}
            client_socket.send(identifier.encode())
            # add the device of the client to the right place in the updates map
            updates_map[identifier].update({computerIdentifier: []})
            print("updates map: ", updates_map)
            print(identifier)

            # if new client - get dir
            if newClient == 1:
                msg_len = client_socket.recv(12).decode()
                directory_name = client_socket.recv(int(msg_len)).decode()
                folder_names_map[identifier] = directory_name
                directory_path = os.path.join(identifier, directory_name)
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
                        msg_len = client_socket.recv(12).decode()  # recive relpath length
                        if msg_len == 'finish_files':
                            break
                        relpath = client_socket.recv(int(msg_len)).decode()  # recive relpath
                        dst_path = os.path.join(directory_path, relpath)
                        length = int(client_socket.recv(12).decode())  # recive file length
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
            # if old client with new device - transfer dir
            else:
                directory = identifier
                msg_len = str(len(folder_names_map[identifier])).zfill(12)
                client_socket.send(msg_len.encode())
                client_socket.send(folder_names_map[identifier].encode())
                for path, dirs, files in os.walk(directory, topdown=True):
                    # send all dirs
                    for dir in dirs:
                        direname = os.path.join(path, dir)
                        relpath = os.path.relpath(direname, directory)
                        msg_len = str(len(relpath)).zfill(12)
                        client_socket.send(msg_len.encode())
                        client_socket.send(relpath.encode())
                    client_socket.send("finish_dires".encode())
                    # send all files
                    for file in files:
                        filename = os.path.join(path, file)
                        relpath = os.path.relpath(filename, directory)
                        msg_len = str(len(relpath)).zfill(12)
                        client_socket.send(msg_len.encode())
                        client_socket.send(relpath.encode())
                        filesize = os.path.getsize(filename)
                        msg_len = str(filesize).zfill(12)
                        client_socket.send(msg_len.encode())
                        with open(filename, 'rb') as f:
                            while True:
                                data = f.read(LIMITED_SIZE)
                                if not data: break
                                client_socket.sendall(data)
                    client_socket.send("finish_files".encode())
                print('Done.')
                client_socket.send("finish_all!!".encode())
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
                    for device in updates_map[identifier]:
                        if computerIdentifier != device:
                            updates_map[identifier][device].append([is_directory, event_type, relpath])

                # case of created event
                elif event_type == 'created':
                    msg_len = client_socket.recv(12).decode()  # receive relpath length
                    relpath = client_socket.recv(int(msg_len)).decode() # receive relpath
                    dst_path = os.path.join(directory_path, relpath)
                    is_directory = client_socket.recv(1).decode()  # receive is_directory
                    for device in updates_map[identifier]:
                        if computerIdentifier != device:
                            updates_map[identifier][device].append([is_directory, event_type, relpath])
                    if is_directory == '1':
                        os.makedirs(dst_path)
                    else:
                        length = int(client_socket.recv(12).decode())  # receive file length
                        # Read the data in chunks so it can handle large files.
                        with open(dst_path, 'w') as f:
                            while length:
                                msg_len = min(length, LIMITED_SIZE)
                                data = client_socket.recv(msg_len).decode()
                                if not data: break
                                f.write(data)
                                length -= len(data)
                            """else:  # only runs if while doesn't break and length==0
                                print('Complete')
                                continue
                                # socket was closed early.
                        print('Incomplete')
                        break"""

                elif event_type == 'moved':
                    msg_len = client_socket.recv(12).decode()  # receive relpath length
                    src_relpath = client_socket.recv(int(msg_len)).decode()  # receive relpath
                    src_path = os.path.join(directory_path, src_relpath)
                    msg_len = client_socket.recv(12).decode()  # receive relpath length
                    dst_relpath = client_socket.recv(int(msg_len)).decode()  # receive relpath
                    dst_path = os.path.join(directory_path, dst_relpath)
                    os.rename(src_path, dst_path)
                    for device in updates_map[identifier]:
                        if computerIdentifier != device:
                            # notice: in 'moved' event the order of the parameters is different!
                            updates_map[identifier][device].append([event_type, src_relpath, dst_relpath])

            for event in updates_map[identifier][computerIdentifier]:
                if event[1] == 'deleted':
                    event_type = 'deleted'
                    msg_len = str(len(event_type)).zfill(12)
                    client_socket.send(msg_len.encode())
                    client_socket.send(event[1].encode())
                    relpath = event[2]
                    msg_len = str(len(relpath)).zfill(12)
                    client_socket.send(msg_len.encode())
                    client_socket.send(relpath.encode())
                    is_directory = '0'
                    if event[0] == '1':
                        is_directory = '1'
                    client_socket.send(is_directory.encode())
                    updates_map[identifier][computerIdentifier].remove(event)

                elif event[1] == 'created':
                    event_type = 'created'
                    msg_len = str(len(event_type)).zfill(12)
                    client_socket.send(msg_len.encode())  # send event_type length
                    client_socket.send(event_type.encode())  # send event type
                    relpath = event[2]
                    msg_len = str(len(relpath)).zfill(12)
                    client_socket.send(msg_len.encode())
                    client_socket.send(relpath.encode())
                    is_directory = '0'
                    if event[0] == '1':
                        is_directory = '1'
                    client_socket.send(is_directory.encode())  # send is_directory
                    if is_directory == '0':
                        src_path = os.path.join(directory_path, relpath)
                        filesize = os.path.getsize(src_path)
                        msg_len = str(filesize).zfill(12)
                        client_socket.send(msg_len.encode())
                        with open(src_path, 'rb') as f:
                            while True:
                                data = f.read(LIMITED_SIZE)
                                if not data: break
                                client_socket.sendall(data)
                    updates_map[identifier][computerIdentifier].remove(event)

                elif event[0] == 'moved':
                    event_type = 'moved'
                    msg_len = str(len(event_type)).zfill(12)
                    client_socket.send(msg_len.encode())  # send event_type length
                    client_socket.send(event_type.encode())  # send event type
                    src_relpath = event[1]
                    msg_len = str(len(src_relpath)).zfill(12)
                    client_socket.send(msg_len.encode())
                    client_socket.send(src_relpath.encode())
                    dst_relpath = event[2]
                    msg_len = str(len(dst_relpath)).zfill(12)
                    client_socket.send(msg_len.encode())
                    client_socket.send(dst_relpath.encode())
                    updates_map[identifier][computerIdentifier].remove(event)

            client_socket.send('finish_all!!'.encode())
            client_socket.close()


if __name__ == "__main__":
    main()