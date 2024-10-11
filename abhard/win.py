import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import subprocess
from app import app
from waitress import serve
from sysutils import config
import sys


class AbhardService(win32serviceutil.ServiceFramework):
    _svc_name_ = "Abhard"
    _svc_display_name_ = "Abacus' Abhard Service"
    _svc_description_ = (
        "This is a proxy service to work with various hardware and provide "
        "unified API for Abacus."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.run_flask_app()

    def run_flask_app(self):
        serve(app, host="0.0.0.0", port=config["webservice"]["port"])


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AbhardService)
    if "install" in sys.argv:
        service_name = "Abhard"
        subprocess.run(f"sc start {service_name}", shell=True, check=True)
        subprocess.run(
            f"sc config {service_name} start= auto", shell=True, check=True
        )
        subprocess.run(
            f"sc failure {service_name} reset= 60 actions= restart/60000",
            shell=True,
        )
