import threading
import os
import time
from sysutils import main_logger, scan_logger
import string
import socket
import serial

# the last 5 chars are '\t\n\r\x0b\x0c', we dont want them in scanned code
printablenows = string.printable[:-5]
separators = "\t\n\r\x0b\x0c\00"


class TCPSocketThread(threading.Thread):
    connected_clients = set()
    clients_lock = threading.Lock()
    active_client = None

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
        scan_logger.info(f"Starting TCP server on {self.host}:{self.port}")
        self.server_socket.settimeout(0.5)
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                with self.clients_lock:
                    self.connected_clients.add(client_socket)
                scan_logger.info(f"Client connected: {addr}")
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
                message = data.decode().strip()
                scan_logger.info(f"Received message: {message}")
                if message.strip() == "act":
                    with self.clients_lock:
                        self.active_client = client_socket
                    self.unicast_message("ack")
                else:
                    pass
                    # This line confuses current client implementation
                    # client_socket.sendall(f"Echo: {message}\r\n".encode())
        except OSError:
            pass
        except UnicodeDecodeError:
            pass
        finally:
            with self.clients_lock:
                self.connected_clients.remove(client_socket)
                if self.active_client == client_socket:
                    self.active_client = None
            client_socket.close()
            scan_logger.info("Client disconnected")

    def stop(self):
        self.running = False
        self.server_socket.close()
        main_logger.info(f"TCP socket {self.name} stopped")

    def unicast_message(self, message):
        with self.clients_lock:
            if self.active_client in self.connected_clients:
                try:
                    self.active_client.send((message + "\r\n").encode())
                    scan_logger.info(
                        f"Sent message {message} to active client."
                    )
                except OSError:
                    self.connected_clients.remove(self.active_client)
                    self.active_client.close()
                    self.active_client = None
                    scan_logger.info(
                        f"Active client disconnected. Message {message} lost."
                    )
            else:
                scan_logger.info(f"No active client to send {message} to.")


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
                main_logger.info(f"Thread {self.name} stopped")
                exit(0)
            try:
                ser = serial.Serial(
                    port=self.device,
                    baudrate=9600,
                    timeout=1  # Non-blocking read with a timeout of 1 second
                )
                scan_logger.info(f"Started {self.device} watching")
                while self.running:
                    if ser.in_waiting:
                        data = ser.read(ser.in_waiting).decode("utf-8")
                        data = "".join(filter(lambda x: x in printablenows, data))
                        scan_logger.info(f"Got {data} from {self.device}")
                        self.tcpthread.unicast_message(f"{data}")
                    '''
                with open(self.device, "r") as file:
                    scan_logger.info(f"Started {self.device} watching")
                    buf = ""
                    poller = select.poll()
                    poller.register(file, select.POLLIN)
                    while self.running:
                        events = poller.poll(0.1)
                        if not events:
                            continue
                        for _, flag in events:
                            if flag & select.POLLERR or flag & select.POLLHUP:
                                raise OSError("Device was disconnected")
                            if flag & select.POLLIN:
                                while c := file.read(1):
                                    buf += c
                                    if c in separators:
                                        break
                                buf = "".join(
                                    filter(lambda x: x in printablenows, buf)
                                )
                                if len(buf):
                                    scan_logger.info(
                                        f"Got {buf} from {self.device}"
                                    )
                                    self.tcpthread.unicast_message(f"{buf}")
                                    buf = ""
                    '''
                    if not os.path.exists(self.device):
                        scan_logger.warning(f"{self.device} was disconnected")
                        break
            except KeyboardInterrupt:
                self.tcpthread.running = False
                self.tcpthread.stop()
                self.running = False
            except SystemExit:
                self.tcpthread.running = False
                self.tcpthread.stop()
                self.running = False
            except OSError as e:
                scan_logger.warning(f"OSError {e} in {self.device} thread.")
            except Exception as e:
                scan_logger.warning(f"Exception {e} in {self.device} thread.")
        main_logger.info(f"Thread watching {self.device} was stopped")
