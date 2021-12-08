import socket
import sys
import os
import watchdog
import time
import string
import random
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LIMITED_SIZE = 1024
# global computerIdentifier


class Handler(FileSystemEventHandler):

    events_list = []

    def on_deleted(self, event):
        self.events_list.append(event)

    def on_created(self, event):
        self.events_list.append(event)

    def on_moved(self, event):
        self.events_list.append(event)

    # def on_modified(self, event):
    #    self.events_list.append(event)

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((sys.argv[1], int(sys.argv[2])))
        server_socket.send(computerIdentifier.encode())
        msg_len = str(len(self.events_list)).zfill(12)
        server_socket.send(msg_len.encode())

        for event in self.events_list:
            if event.event_type == 'deleted':
                event_type = 'deleted'
                msg_len = str(len(event_type)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(event_type.encode())
                relpath = os.path.relpath(event.src_path, directory_path)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
                is_directory = '0'
                if event.is_directory:
                    is_directory = '1'
                server_socket.send(is_directory.encode())
                self.events_list.remove(event)

            elif event.event_type == 'created':
                event_type = 'created'
                msg_len = str(len(event_type)).zfill(12)
                server_socket.send(msg_len.encode())    # send event_type length
                server_socket.send(event_type.encode()) # send event type
                relpath = os.path.relpath(event.src_path, directory_path)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
                is_directory = '0'
                if event.is_directory:
                    is_directory = '1'
                server_socket.send(is_directory.encode())  # send is_directory
                if is_directory == '0':
                    filesize = os.path.getsize(event.src_path)
                    msg_len = str(filesize).zfill(12)
                    server_socket.send(msg_len.encode())
                    with open(event.src_path, 'rb') as f:
                        while True:
                            data = f.read(LIMITED_SIZE)
                            if not data: break
                            server_socket.sendall(data)
                self.events_list.remove(event)


        server_socket.close()


def main():
    global directory_path
    timeout = int(sys.argv[4])

    # 1.connect to the server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((sys.argv[1], int(sys.argv[2])))

    # 2.get new identifier if need or send the identifier that get from the input
    global computerIdentifier
    computerIdentifier = '0' * 128
    server_socket.send(computerIdentifier.encode())
    computerIdentifier = server_socket.recv(128).decode()
    newclient = 0
    if len(sys.argv) == 5:
        newclient = 1
    identifier = '0'
    if len(sys.argv) == 6:
        identifier = sys.argv[5]
    server_socket.send(identifier.encode())
    identifier = server_socket.recv(128).decode()
    print('identifier is: ', identifier)

    # 3.if new client - send directory
    if newclient == 1:
        # global directory
        directory = sys.argv[3]
        head, tail = os.path.split(directory)
        msg_len = str(len(tail)).zfill(12)
        server_socket.send(msg_len.encode())
        server_socket.send(tail.encode())
        for path, dirs, files in os.walk(directory, topdown=True):
            for dir in dirs:
                direname = os.path.join(path, dir)
                relpath = os.path.relpath(direname, directory)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
            server_socket.send("finish_dires".encode())
            for file in files:
                filename = os.path.join(path, file)
                relpath = os.path.relpath(filename, directory)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
                filesize = os.path.getsize(filename)               
                msg_len = str(filesize).zfill(12)
                server_socket.send(msg_len.encode())
                with open(filename, 'rb') as f:
                    while True:
                        data = f.read(LIMITED_SIZE)
                        if not data: break
                        server_socket.sendall(data)
            server_socket.send("finish_files".encode())
        print('Done.')
        directory_path = sys.argv[3]
        server_socket.send("finish_all!!".encode())
    # 4.if the client already exist - get directory
    else:
        msg_len = server_socket.recv(12).decode()
        directory_name = server_socket.recv(int(msg_len)).decode()
        cwd = os.getcwd()
        directory_path = os.path.join(cwd, directory_name)
        # os.makedirs(identifier, exist_ok=True)
        with server_socket, server_socket.makefile('rb') as clientfile:
            while True:
                raw = clientfile.readline()
                if not raw: break  # no more files, server closed connection.

                filename = raw.strip().decode()
                length = int(clientfile.readline())
                print(f'Downloading {filename}...\n  Expecting {length:,} bytes...', end='', flush=True)

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

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    event_handler = Handler()
    observer = Observer()
    observer.schedule(event_handler, directory_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(timeout)
            event_handler.run()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
