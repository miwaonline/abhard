from flask import Flask
import signal
import sys
import os
import traceback
from waitress import serve
from sysutils import main_logger, config
from api import api, rro_objects, tcpsocket_threads, scaner_threads

if os.name == "nt":
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

app = Flask("abhard")
app.register_blueprint(api)


def initialize_rro_objects():
    if config.get("rro"):
        try:
            from rro_eusign import EUSign

            for rro in config["rro"]:
                rroobj = EUSign(rro["id"], rro["keyfile"], rro["keypass"])
                rro_objects[rro["id"]] = rroobj
                main_logger.info(f"Initialized RRO {rro['id']}")
        except Exception:
            main_logger.error(f"Error initializing RRO: {traceback.format_exc()}",
                              exc_info=traceback.format_exc())


def initialize_scaner_threads():
    if config.get("scaner"):
        from scaner_thread import ScanerThread, TCPSocketThread

        for scaner in config["scaner"]:
            if scaner["type"] == "serial":
                main_logger.info(f"Starting TCP thread for {scaner['name']}")
                tcpthread = TCPSocketThread(
                    scaner["name"], scaner["socket_port"]
                )
                tcpsocket_threads[scaner["name"]] = tcpthread
                tcpthread.start()
                main_logger.info(
                    f"Starting listening thread for {scaner['name']}"
                )
                thread = ScanerThread(
                    scaner["name"], scaner["device"], tcpthread
                )
                scaner_threads[scaner["name"]] = thread
                thread.start()


def startup_tasks():
    main_logger.info("Initializing RRO objects and Scaner threads...")
    initialize_rro_objects()
    initialize_scaner_threads()


def signal_handler(sig, frame):
    main_logger.info("Shutting down gracefully...")
    for thread in scaner_threads.values():
        thread.running = False
    for thread in tcpsocket_threads.values():
        thread.stop()
        thread.join()
    sys.exit(0)


def main():
    with app.app_context():
        startup_tasks()
    # Start Flask app
    serve(app, host="0.0.0.0", port=config["webservice"]["port"])


def run_service():
    with app.app_context():
        startup_tasks()
    try:
        serve(app, host="0.0.0.0", port=config["webservice"]["port"])
    except Exception as e:
        if os.name == "nt":
            servicemanager.LogErrorMsg(str(e))
            servicemanager.LogErrorMsg(str(e.args))
            servicemanager.LogErrorMsg(traceback.format_exc())
        os._exit(-1)


if os.name == "nt":

    class WindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = "Abhard"
        _svc_display_name_ = "Abhard Abacus Service"
        _svc_description_ = ("Application that works with different hardware "
                             "and provides unified API for Abacus.")

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.hWaitStop)
            signal_handler(signal.SIGINT, None)

        def SvcDoRun(self):
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                                  servicemanager.PYS_SERVICE_STARTED,
                                  (self._svc_name_, ''))
            self.run = True
            run_service()

    if __name__ == "__main__":
        if len(sys.argv) > 1 and sys.argv[1] in ["install", "update", "remove"]:
            win32serviceutil.HandleCommandLine(WindowsService)
        else:
            main()
else:
    if __name__ == "__main__":
        main()
