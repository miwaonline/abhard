from sysutils import prnt_logger
from escpos import printer


def configure_printer(printercfg):
    dummy = False
    printtype = printercfg["type"].lower()
    if printtype == "usb" and printer.Usb.is_usable():
        # We can also force encoding here by passing the encoding parameter:
        # magic_encode_args={"encoding": "cp866"},
        # However its much better to use right profile instead
        p = printer.Usb(
            idProduct=printercfg["product_id"],
            idVendor=printercfg["vendor_id"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured USB printer")
    elif printtype == "serial":
        p = printer.Serial(
            devfile=printercfg["device"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured serial printer")
    elif printtype == "file":
        p = printer.File(
            filename=printercfg["device"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured file printer")
    elif (
        printtype == "network" and printer.Network.is_usable()
    ):
        p = printer.Network(
            host=printercfg["host"],
            port=printercfg["port"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured network printer")
    elif (
        printtype == "cups" and printer.CupsPrinter.is_usable()
    ):
        p = printer.CupsPrinter(
            name=printercfg["name"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured CUPS printer")
    elif (
        printtype == "windows" and printer.Win32Raw.is_usable()
    ):
        p = printer.Win32Raw(
            name=printercfg["name"],
            profile=printercfg.get("profile", "default"),
        )
        prnt_logger.info("Configured Windows printer")
    elif printtype == "dummy":
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    else:
        if printtype in ["usb", "network", "cups", "windows"]:
            prnt_logger.warning(
                "Printer dependancies are not installed. Falling back to dummy"
                " printer."
            )
        p = printer.Dummy()
        dummy = True
        prnt_logger.info("Configured dummy printer")
    return p, dummy


def render_string(s: str, n=None, align: str = "left"):
    if not n:
        return [s]
    chunks = [s[i: i + n] for i in range(0, len(s), n)]
    if align == "center":
        return [chunk.center(n) for chunk in chunks]
    elif align == "right":
        return [chunk.rjust(n) for chunk in chunks]
    else:
        return chunks


def print_header(prn: printer.Dummy, doc_header: dict, width=None):
    prn.set(align="left" if width else "center", bold=True)
    prn.textln(render_string(doc_header["title"], width, "center")[0])
    prn.textln(render_string(doc_header["date"], width, "center")[0])
    prn.textln(render_string(doc_header["time"], width, "center")[0])
    if doc_header.get("barcode"):
        prn.barcode(
            code=doc_header["barcode"]["value"],
            bc=doc_header["barcode"]["type"],
            pos="OFF",
            align_ct=not width,
        )
    if doc_header.get("qr"):
        prn.qr(doc_header["qr"]["value"], center=not width)


def print_footer(prn: printer.Dummy, doc_footer: dict, width=None):
    if doc_footer.get("barcode"):
        prn.barcode(
            code=doc_footer["barcode"]["value"],
            bc=doc_footer["barcode"]["type"],
            pos="OFF",
            align_ct=not width,
        )
    if doc_footer.get("qr"):
        prn.qr(doc_footer["qr"]["value"], center=not width)
    prn.set(align="left" if width else "right", bold=False)
    val = f'Всього: {doc_footer["summ"]:.2f}'
    prn.textln(render_string(val, width, "right")[0])
    if doc_footer.get("discount"):
        val = f'Знижка: {doc_footer["discount"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])
        val = f'Разом: {doc_footer["total"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])


def print_content(prn: printer.Dummy, doc_content: dict, width=None):
    for line in doc_content:
        prn.set(align="left", bold=False)
        name_render = (render_string(f'{line["name"]}', width))
        for name_line in name_render:
            prn.textln(name_line)
        val = f'{line["amount"]} x {line["price"]:.2f}'
        if width:
            filler = " " * (width - len(line["code"]) - len(val))
            prn.textln(f'{line["code"]}{filler}{val}')
        else:
            prn.text(f'{line["code"]}')
            prn.set(align="right")
            prn.textln(val)


def print_document(printercfg, doc):
    prnt_logger.info("Configuring printer")
    prn, dummy = configure_printer(printercfg)
    prn.open()
    prnt_logger.info("Printing document")
    prnt_logger.info(doc)
    print_header(prn, doc["header"], printercfg.get("width", None))
    print_content(prn, doc["content"], printercfg.get("width", None))
    print_footer(prn, doc["footer"], printercfg.get("width", None))
    prn.cut()
    if dummy:
        prnt_logger.info(prn.output())
    else:
        prn.close()
    prnt_logger.info("Document printed")
    return {"result": "OK"}
