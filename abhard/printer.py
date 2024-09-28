from sysutils import prnt_logger
from escpos import printer


def configure_printer(printercfg):
    dummy = False
    if printercfg["type"].lower() == "usb":
        p = printer.Usb(
            idProduct=printercfg["product_id"],
            idVendor=printercfg["vendor_id"],
        )
        prnt_logger.info("Configured USB printer")
    elif printercfg["type"].lower() == "serial":
        p = printer.Serial(
            devfile=printercfg["device"],
        )
        prnt_logger.info("Configured serial printer")
    elif printercfg["type"].lower() == "file":
        p = printer.File(
            filename=printercfg["device"],
        )
        prnt_logger.info("Configured file printer")
    elif printercfg["type"].lower() == "network":
        p = printer.Network(
            host=printercfg["host"],
            port=printercfg["port"],
        )
        prnt_logger.info("Configured network printer")
    elif printercfg["type"].lower() == "cups":
        p = printer.CupsPrinter(
            name=printercfg["name"],
        )
        prnt_logger.info("Configured CUPS printer")
    elif printercfg["type"].lower() == "windows":
        p = printer.Win32Raw(
            name=printercfg["name"],
        )
        prnt_logger.info("Configured Windows printer")
    elif printercfg["type"].lower() == "dummy":
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    else:
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    return p, dummy


def print_document(printercfg, doc):
    p, dummy = configure_printer(printercfg)
    p.open()
    p.set(align="center", bold=True)
    p.text(doc["header"]["title"] + "\n")
    p.text(doc["header"]["date"] + "\n")
    p.set(align="left", bold=False)
    for line in doc["body"]:
        p.text(line + "\n")
    p.set(align="right", bold=True)
    p.text(doc["footer"] + "\n")
    p.cut()
    if not dummy:
        p.close()
    return {"result": "OK"}
