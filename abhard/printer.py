from sysutils import prnt_logger
from escpos import printer


def configure_printer(printercfg):
    dummy = False
    if printercfg["type"].lower() == "usb" and printer.Usb.is_usable():
        # We can also force encoding here by passing the encoding parameter:
        # magic_encode_args={"encoding": "cp866"},
        # However its much better to use right profile instead
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
        printercfg["type"].lower() == "network" and printer.Network.is_usable()
    ):
        p = printer.Network(
            host=printercfg["host"],
            port=printercfg["port"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured network printer")
    elif (
        printercfg["type"].lower() == "cups" and printer.CupsPrinter.is_usable()
    ):
        p = printer.CupsPrinter(
            name=printercfg["name"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured CUPS printer")
    elif (
        printercfg["type"].lower() == "windows" and printer.Win32Raw.is_usable()
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
    return p, dummy


def print_document(printercfg, doc):
    prnt_logger.info("Configuring printer")
    prn, dummy = configure_printer(printercfg)
    prn.open()
    prnt_logger.info("Printing document")
    prnt_logger.info(doc)
    if printercfg.get("width"):
        print_doc_softrender(prn, doc, printercfg["width"])
    else:
        print_doc_native(prn, doc)
    prn.cut()
    if not dummy:
        prn.close()
    prnt_logger.info("Document printed")
    return {"result": "OK"}


def render_string(s: str, n: int, align: str = "left"):
    chunks = [s[i: i + n] for i in range(0, len(s), n)]
    if align == "center":
        return [chunk.center(n) for chunk in chunks]
    elif align == "right":
        return [chunk.rjust(n) for chunk in chunks]
    else:
        return chunks


def print_doc_native(prn: printer.Dummy, doc: dict):
    prn.set(align="center", bold=True)
    prn.textln(doc["header"]["title"])
    prn.textln(doc["header"]["date"])
    prn.textln(doc["header"]["time"])
    if doc["header"].get("barcode"):
        prn.barcode(
            code=doc["header"]["barcode"]["value"],
            bc=doc["header"]["barcode"]["type"],
            pos="OFF",
        )
    if doc["header"].get("qr"):
        prn.qr(doc["header"]["qr"]["value"])
    for line in doc["content"]:
        prn.set(align="left", bold=False)
        prn.textln(f'{line["name"]}')
        prn.text(f'{line["code"]}')
        prn.set(align="right")
        prn.textln('{line["amount"]} x {line["price"]:.2f}')
    if doc["footer"].get("barcode"):
        prn.barcode(
            code=doc["footer"]["barcode"]["value"],
            bc=doc["footer"]["barcode"]["type"],
            pos="OFF",
        )
    if doc["footer"].get("qr"):
        prn.qr(doc["footer"]["qr"]["value"])
    prn.set(align="right", bold=False)
    prn.textln(f'Всього: {doc["footer"]["summ"]:.2f}')
    if doc["footer"].get("discount"):
        prn.textln(f'Знижка: {doc["footer"]["discount"]:.2f}')
        prn.textln(f'Разом: {doc["footer"]["total"]:.2f}')


def print_doc_softrender(prn: printer.Dummy, doc: dict, width: int):
    prn.set(align="left", bold=True)
    for line in render_string(doc["header"]["title"], width, "center"):
        prn.textln(line)
    for line in render_string(doc["header"]["date"], width, "center"):
        prn.textln(line)
    for line in render_string(doc["header"]["time"], width, "center"):
        prn.textln(line)
    if doc["header"].get("barcode"):
        prn.barcode(
            code=doc["header"]["barcode"]["value"],
            bc=doc["header"]["barcode"]["type"],
            pos="OFF",
            align_ct=False,
        )
    if doc["header"].get("qr"):
        prn.qr(doc["header"]["qr"]["value"], center=False)
    prn.set(align="left", bold=False)
    for item in doc["content"]:
        for line in render_string(f'{item["name"]}', width):
            prn.textln(line)
        val = f'{item["amount"]} x {item["price"]:.2f}'
        filler = " " * (width - len(item["code"]) - len(val))
        prn.textln(
            f'{item["code"]}{filler}{val}'
        )
    if doc["footer"].get("barcode"):
        prn.barcode(
            code=doc["footer"]["barcode"]["value"],
            bc=doc["footer"]["barcode"]["type"],
            pos="OFF",
            align_ct=False,
        )
    if doc["footer"].get("qr"):
        prn.qr(doc["footer"]["qr"]["value"], center=False)
    prn.set(align="left", bold=False)
    for line in render_string(
        f'Всього: {doc["footer"]["summ"]:.2f}', width, "right"
    ):
        prn.textln(line)
    if doc["footer"].get("discount"):
        for line in render_string(
            f'Знижка: {doc["footer"]["discount"]:.2f}', width, "right"
        ):
            prn.textln(line)
        for line in render_string(
            f'Разом: {doc["footer"]["total"]:.2f}', width, "right"
        ):
            prn.textln(line)
