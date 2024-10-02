from sysutils import prnt_logger
from escpos import printer


def configure_printer(printercfg):
    dummy = False
    if printercfg["type"].lower() == "usb" and printer.Usb.is_usable():
        p = printer.Usb(
            idProduct=printercfg["product_id"],
            idVendor=printercfg["vendor_id"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured USB printer")
    elif printercfg["type"].lower() == "serial":
        p = printer.Serial(
            devfile=printercfg["device"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured serial printer")
    elif printercfg["type"].lower() == "file":
        p = printer.File(
            filename=printercfg["device"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured file printer")
    elif (
        printercfg["type"].lower() == "network"
        and printer.Network.is_usable()
    ):
        p = printer.Network(
            host=printercfg["host"],
            port=printercfg["port"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured network printer")
    elif (
        printercfg["type"].lower() == "cups"
        and printer.CupsPrinter.is_usable()
    ):
        p = printer.CupsPrinter(
            name=printercfg["name"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured CUPS printer")
    elif (
        printercfg["type"].lower() == "windows"
        and printer.Win32Raw.is_usable()
    ):
        p = printer.Win32Raw(
            name=printercfg["name"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured Windows printer")
    elif printercfg["type"].lower() == "dummy":
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    else:
        if printercfg["type"].lower() in ["usb", "network", "cups", "windows"]:
            prnt_logger.warning(
                "Printer dependancies are not installed. Falling back to dummy"
                " printer."
            )
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    if printercfg.get("width"):
        p.set(width=printercfg["width"])
    return p, dummy


def print_document(printercfg, doc):
    prnt_logger.info("Configuring printer")
    p, dummy = configure_printer(printercfg)
    p.open()
    prnt_logger.info("Printing document")
    prnt_logger.info(doc)
    p.set(align="center", bold=True)
    p.textln(doc["header"]["title"])
    p.textln(doc["header"]["date"])
    p.textln(doc["header"]["time"])
    p.set(align="left", bold=False)
    for gname, gcode, gprice, gqty in doc["content"]:
        p.textln(f'{gname} ({gcode}) {gprice} x {gqty}')
    p.set(align="right", bold=True)
    p.textln(f'{doc["footer"]["total"]}')
    p.textln(f'{doc["footer"]["discount"]}')
    p.cut()
    if not dummy:
        p.close()
    prnt_logger.info("Document printed")
    return {"result": "OK"}
