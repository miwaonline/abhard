import threading
import os
import select
import time
from sysutils import logger
import string
import asyncio
import websockets


connected_clients = set()
# the last 5 chars are '\t\n\r\x0b\x0c', we dont want them in scanned code
printablenows = string.printable[:-5]


async def scanner_callback(data):
    logger.info(f"Received {data} from scanner")
    if connected_clients:
        logger.info(f"Sending {data} to clients")
        tasks = [
            asyncio.create_task(client.send(data))
            for client in connected_clients
        ]
        await asyncio.gather(*tasks)


async def websocket_handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received message: {message}")
            await websocket.send(f"Echo: {message}")
    finally:
        connected_clients.remove(websocket)


class WebSocketServerThread(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.loop = None
        self.server = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = websockets.serve(
            websocket_handler, "localhost", self.port
        )
        self.loop.run_until_complete(self.server)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class ScanerThread(threading.Thread):
    def __init__(self, scaner_id, device):
        threading.Thread.__init__(self)
        self.scaner_id = scaner_id
        self.device = device
        self.running = True
        self.callback = scanner_callback

    def run(self):
        while self.running:
            while self.running and not os.path.exists(self.device):
                time.sleep(0.1)
            if not self.running:
                logger.info(f"Thread {self.scaner_id} stopped")
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
                                logger.info(f"Got {buf=} from {self.device}")
                                asyncio.run(self.callback(buf))
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
