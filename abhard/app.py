from flask import Flask
import signal
import sys
from waitress import serve
from sysutils import main_logger, config
from rro_eusign import EUSign
from scaner_thread import ScanerThread, TCPSocketThread
from api import api, rro_objects, tcpsocket_threads, scaner_threads

app = Flask("abhard")
app.register_blueprint(api)

# Initialize RRO objects
for rro in config["rro"]:
    rroobj = EUSign(rro["id"], rro["keyfile"], rro["keypass"])
    rro_objects[rro["id"]] = rroobj
    main_logger.info(f"Initialized RRO {rro['id']}")

# Initialize Scaner threads
for scaner in config["scaner"]:
    if scaner["type"] == "serial":
        main_logger.info(f"Starting TCP socket thread for {scaner['name']}")
        tcpthread = TCPSocketThread(
            scaner["name"], scaner["socket_port"]
        )
        tcpsocket_threads[scaner["name"]] = tcpthread
        tcpthread.start()
        main_logger.info(f"Starting listening thread for {scaner['name']}")
        thread = ScanerThread(scaner["name"], scaner["device"], tcpthread)
        scaner_threads[scaner["name"]] = thread
        thread.start()


def signal_handler(sig, frame):
    main_logger.info("Shutting down gracefully...")
    for thread in scaner_threads.values():
        thread.running = False
    for thread in tcpsocket_threads.values():
        thread.stop()
        thread.join()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=config["webservice"]["port"])
    serve(app, host="0.0.0.0", port=config["webservice"]["port"])
