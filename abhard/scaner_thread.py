import threading
import os
import select
import time
from sysutils import logger
import string
import socket


# the last 5 chars are '\t\n\r\x0b\x0c', we dont want them in scanned code
printablenows = string.printable[:-5]


class TCPSocketThread(threading.Thread):
    connected_clients = set()
    clients_lock = threading.Lock()

    def __init__(self, name, port):
        super().__init__()
        self.name = name
        self.host = "0.0.0.0"
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

    def run(self):
        logger.info(f"Starting TCP server on {self.host}:{self.port}")
        self.server_socket.settimeout(0.5)
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                with self.clients_lock:
                    self.connected_clients.add(client_socket)
                logger.info(f"Client connected: {addr}")
                threading.Thread(
                    target=self.client_handler, args=(client_socket,)
                ).start()
            except socket.timeout:
                continue  # continue on timeout
            except OSError:
                break  # exit the loop if socket is closed

    def client_handler(self, client_socket):
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                logger.info(f"Received message: {data.decode()}")
                client_socket.sendall(f"Echo: {data.decode()}".encode())
        except OSError:
            pass
        except UnicodeDecodeError:
            pass
        finally:
            with self.clients_lock:
                self.connected_clients.remove(client_socket)
            client_socket.close()
            logger.info("Client disconnected")

    def stop(self):
        self.running = False
        self.server_socket.close()
        logger.info(f"TCP socket {self.name} stopped")

    def broadcast_message(self, message):
        with self.clients_lock:
            for client in list(self.connected_clients):
                try:
                    client.send(message.encode())
                except OSError:
                    with self.clients_lock:
                        self.connected_clients.remove(client)
                    client.close()


class ScanerThread(threading.Thread):
    def __init__(self, name, device, tcpthread):
        threading.Thread.__init__(self)
        self.name = name
        self.device = device
        self.running = True
        self.tcpthread = tcpthread

    def run(self):
        while self.running:
            while self.running and not os.path.exists(self.device):
                time.sleep(0.1)
            if not self.running:
                logger.info(f"Thread {self.name} stopped")
                exit(0)
            try:
                with open(self.device, "r") as file:
                    logger.info(f"Started {self.device} watching")
                    buf = ""
                    while self.running:
                        ready, _, _ = select.select([file], [], [], 0.1)
                        if file in ready:
                            while c := file.read(1):
                                buf += c
                                if c == "\00":
                                    break
                            buf = "".join(
                                filter(lambda x: x in printablenows, buf)
                            )
                            if len(buf):
                                logger.debug(f"Got {buf=} from {self.device}")
                                self.tcpthread.broadcast_message(f"{buf}\r\n")
                                buf = ""
                    if not os.path.exists(self.device):
                        logger.warning(f"{self.device} was disconnected")
                        break
            except (KeyboardInterrupt, SystemExit, Exception) as e:
                if isinstance(e, KeyboardInterrupt):
                    self.running = False
                elif isinstance(e, SystemExit):
                    self.running = False
                else:
                    logger.warning(f"{e} in thread watching {self.device}")
        logger.info(f"Thread watching {self.device} was stopped")
