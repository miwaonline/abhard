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


def print_header(
    prn: printer.Dummy, doc_header: dict, width=None, align_center=True
):
    align = "center" if align_center else "left"
    prn.set(align=align, bold=True)
    prn.textln(
        doc_header["title"]
        if not width
        else render_string(doc_header["title"], width, align)[0]
    )
    prn.textln(
        doc_header["date"]
        if not width
        else render_string(doc_header["date"], width, align)[0]
    )
    prn.textln(
        doc_header["time"]
        if not width
        else render_string(doc_header["time"], width, align)[0]
    )
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
    prn.set(align="right" if not width else "left", bold=False)
    prn.textln(
        f'Всього: {doc_footer["summ"]:.2f}'
        if not width
        else render_string(
            f'Всього: {doc_footer["summ"]:.2f}', width, "right"
        )[0]
    )
    if doc_footer.get("discount"):
        prn.textln(
            f'Знижка: {doc_footer["discount"]:.2f}'
            if not width
            else render_string(
                f'Знижка: {doc_footer["discount"]:.2f}', width, "right"
            )[0]
        )
        prn.textln(
            f'Разом: {doc_footer["total"]:.2f}'
            if not width
            else render_string(
                f'Разом: {doc_footer["total"]:.2f}', width, "right"
            )[0]
        )


def print_content(prn: printer.Dummy, doc_content: dict, width=None):
    for line in doc_content:
        prn.set(align="left", bold=False)
        name_render = (
            [line["name"]]
            if not width
            else render_string(f'{line["name"]}', width)
        )
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


def print_doc_native(prn: printer.Dummy, doc: dict):
    print_header(prn, doc["header"])
    print_content(prn, doc["content"])
    print_footer(prn, doc["footer"])


def print_doc_softrender(prn: printer.Dummy, doc: dict, width: int):
    print_header(prn, doc["header"], width, align_center=False)
    print_content(prn, doc["content"], width)
    print_footer(prn, doc["footer"], width)
