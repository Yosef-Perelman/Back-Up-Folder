import socket
import sys
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

LIMITED_SIZE = 8000  # Limited size for sends messages in segments


class Handler(FileSystemEventHandler):

    flag = 0  # Flag that determine if listen to the watchdog updates
    events_list = []  # List of events that receives from the watchdog

    def on_deleted(self, event):
        if self.flag == 0:
            self.events_list.append(event)

    def on_created(self, event):
        if self.flag == 0:
            self.events_list.append(event)

    def on_moved(self, event):
        if self.flag == 0:
            self.events_list.append(event)

    # This method do the communication with the server - send and receive updates
    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((sys.argv[1], int(sys.argv[2])))
        server_socket.send(computerIdentifier.encode())
        # Send the length of the events_list
        msg_len = str(len(self.events_list)).zfill(12)
        server_socket.send(msg_len.encode())

        # For every event send the relevant information:
        # is directory, event type, path to the file/dir, and the data itself if needed
        # I will explain in the first case of 'deleted', and in the same parts of
        # the rest cases its same.
        for event in self.events_list:
            if event.event_type == 'deleted':
                event_type = 'deleted'
                # Send the event type
                msg_len = str(len(event_type)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(event_type.encode())
                # Send the relative path from the main dir to the file/dir
                relpath = os.path.relpath(event.src_path, directory_path)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
                # Send if its dir or file in order to the server will know if he needed to remove the all dir
                is_directory = '0'
                if event.is_directory:
                    is_directory = '1'
                server_socket.send(is_directory.encode())

            elif event.event_type == 'created':
                event_type = 'created'
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
                # If its file send the data from the file
                if is_directory == '0':
                    filesize = os.path.getsize(event.src_path)
                    msg_len = str(filesize).zfill(12)
                    server_socket.send(msg_len.encode())
                    with open(event.src_path, 'rb') as f:
                        while True:
                            # If needed - divides the message into segments
                            data = f.read(LIMITED_SIZE)
                            if not data: break
                            server_socket.sendall(data)

            elif event.event_type == 'moved':
                event_type = 'moved'
                msg_len = str(len(event_type)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(event_type.encode())
                src_relpath = os.path.relpath(event.src_path, directory_path)
                msg_len = str(len(src_relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(src_relpath.encode())
                dst_relpath = os.path.relpath(event.dest_path, directory_path)
                msg_len = str(len(dst_relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(dst_relpath.encode())
        self.events_list.clear()

        # From here until the end of the method the client gets updates from the server.
        # First turn on the flag that says not to listen to the watchdog updates
        self.flag = 1
        msg_len = server_socket.recv(12).decode()  # Recive first event_type length
        while True:
            if msg_len == 'finish_all!!':  # Break statment
                break
            if msg_len == '000000000000':
                msg_len = '0'
            event_type = server_socket.recv(int(msg_len)).decode()  # recive event_type

            # Case of deleted event
            if event_type == 'deleted':
                # Recive relative path
                msg_len = server_socket.recv(12).decode()
                relpath = server_socket.recv(int(msg_len)).decode()
                dst_path = os.path.join(directory_path, relpath)
                is_directory = server_socket.recv(1).decode()
                if is_directory == '1':
                    for root, dirs, files in os.walk(dst_path, topdown=False):
                        for name in files:
                            os.remove(os.path.join(root, name))
                        for name in dirs:
                            os.rmdir(os.path.join(root, name))
                    os.rmdir(dst_path)
                else:
                    os.remove(dst_path)
            # Case of created event
            elif event_type == 'created':
                msg_len = server_socket.recv(12).decode()  # receive relpath length
                relpath = server_socket.recv(int(msg_len)).decode()  # receive relpath
                dst_path = os.path.join(directory_path, relpath)
                is_directory = server_socket.recv(1).decode()  # receive is_directory
                if is_directory == '1':
                    os.makedirs(dst_path)
                else:
                    length = int(server_socket.recv(12).decode())  # receive file length
                    # Read the data in chunks so it can handle large files.
                    with open(dst_path, 'w') as f:
                        while length:
                            msg_len = min(length, LIMITED_SIZE)
                            data = server_socket.recv(msg_len).decode()
                            if not data: break
                            f.write(data)
                            length -= len(data)
            # Case of moved event
            elif event_type == 'moved':
                msg_len = server_socket.recv(12).decode()  # receive relpath length
                src_relpath = server_socket.recv(int(msg_len)).decode()  # receive relpath
                src_path = os.path.join(directory_path, src_relpath)
                msg_len = server_socket.recv(12).decode()  # receive relpath length
                dst_relpath = server_socket.recv(int(msg_len)).decode()  # receive relpath
                dst_path = os.path.join(directory_path, dst_relpath)
                os.rename(src_path, dst_path)
            msg_len = server_socket.recv(12).decode()
        self.flag = 0
        server_socket.close()


def main():
    global directory_path
    timeout = int(sys.argv[4])

    # connect to the server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.connect((sys.argv[1], int(sys.argv[2])))

    # set identifier and computeridentifier
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

    # if new client - transfer dir
    if newclient == 1:
        directory = sys.argv[3]
        # split the directory name and send it
        head, tail = os.path.split(directory)
        msg_len = str(len(tail)).zfill(12)
        server_socket.send(msg_len.encode())
        server_socket.send(tail.encode())
        for path, dirs, files in os.walk(directory, topdown=True):
            # send all dirs
            for dir in dirs:
                direname = os.path.join(path, dir)
                relpath = os.path.relpath(direname, directory)
                msg_len = str(len(relpath)).zfill(12)
                server_socket.send(msg_len.encode())
                server_socket.send(relpath.encode())
            server_socket.send("finish_dires".encode())
            # send all files
            counter = 0
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
                counter += 1
            server_socket.send("finish_files".encode())
        directory_path = sys.argv[3]
        server_socket.send("finish_all!!".encode())
    # if known client from new device - get dir
    else:
        msg_len = server_socket.recv(12).decode()
        directory_name = server_socket.recv(int(msg_len)).decode()
        directory_path = os.path.join(sys.argv[3], directory_name)
        while True:
            msg_len = server_socket.recv(12).decode()
            if msg_len == 'finish_all!!':
                break
            while msg_len != 'finish_dires':
                dirrelpath = server_socket.recv(int(msg_len)).decode()
                dirname = os.path.join(sys.argv[3], dirrelpath)
                os.makedirs(dirname)
                msg_len = server_socket.recv(12).decode()
            while True:
                msg_len = server_socket.recv(12).decode()  # recive relpath length
                if msg_len == 'finish_files':
                    break
                relpath = server_socket.recv(int(msg_len)).decode()  # recive relpath
                dst_path = os.path.join(sys.argv[3], relpath)
                length = int(server_socket.recv(12).decode())  # recive file length
                # Read the data in chunks so it can handle large files.
                with open(dst_path, 'wb') as f:
                    while length:
                        msg_len = min(length, LIMITED_SIZE)
                        data = server_socket.recv(msg_len)
                        if not data: break
                        f.write(data)
                        length -= len(data)
    server_socket.close()


    event_handler = Handler()
    global observer
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
