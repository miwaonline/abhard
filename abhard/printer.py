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


def render_string(s: str, width=None, align: str = "left"):
    if not width:
        return [s]
    chunks = [s[i: i + width] for i in range(0, len(s), width)]
    if align == "center":
        return [chunk.center(width) for chunk in chunks]
    elif align == "right":
        return [chunk.rjust(width) for chunk in chunks]
    else:
        return chunks


def print_header(prn: printer.Dummy, doc_header: dict, width=None):
    def print_field(name):
        if doc_header.get(name):
            prn.textln(render_string(doc_header[name], width, "center")[0])

    prn.set(align="left" if width else "center", bold=True)
    print_field("rro_orgname")
    print_field("rro_pointname")
    print_field("rro_pointaddr")
    print_field("rro_tin")
    print_field("rro_fn")
    print_field("rro_receiptno")
    print_field("title")
    print_field("date")
    print_field("time")
    if doc_header.get("barcode"):
        if doc_header["barcode"]["type"] == "code128":
            barcode = '{B' + doc_header["barcode"]["value"]
        else:
            barcode = doc_header["barcode"]["value"]
        prn.barcode(
            code=barcode,
            bc=doc_header["barcode"]["type"],
            pos="OFF",
            align_ct=not width,
        )
    if doc_header.get("qr"):
        prn.qr(doc_header["qr"]["value"], center=not width)


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
            prn.set(align="left")
            prn.text(f'{line["code"]}')
            prn.set(align="right")
            prn.textln(val)


def print_footer(prn: printer.Dummy, doc_footer: dict, width=None):
    prn.set(align="left" if width else "right", bold=False)
    val = f'Всього: {doc_footer["summ"]:.2f}'
    prn.textln(render_string(val, width, "right")[0])
    if doc_footer.get("discount"):
        val = f'Знижка: {doc_footer["discount"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])
        val = f'До сплати: {doc_footer["total"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])
    if doc_footer.get("cash"):
        val = f'Готівка: {doc_footer["cash"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])
    if doc_footer.get("card"):
        val = f'Картка: {doc_footer["card"]:.2f}'
        prn.textln(render_string(val, width, "right")[0])
    if doc_footer.get("barcode"):
        if doc_footer["barcode"]["type"] == "code128":
            barcode = '{B' + doc_footer["barcode"]["value"]
        else:
            barcode = doc_footer["barcode"]["value"]
        prn.barcode(
            code=barcode,
            bc=doc_footer["barcode"]["type"],
            pos="OFF",
            align_ct=not width,
        )
    if doc_footer.get("qr"):
        prn.qr(doc_footer["qr"]["value"], center=not width)


def print_report_content(prn: printer.Dummy, doc_content: dict, width=None):
    for line in doc_content:
        prn.set(align="left", bold=False)
        name = render_string(f'{line["name"]}', width)[0]
        val = f'{line["price"]:.2f}'
        if width:
            prn.text(name)
            filler = " " * (width - len(name) - len(val))
            prn.textln(f'{filler}{val}')
        else:
            prn.set(align="left")
            prn.textln(name)
            prn.set(align="right")
            prn.textln(val)


def print_report_footer(prn: printer.Dummy, doc_footer: dict, width=None):
    if isinstance(doc_footer, dict):
        if doc_footer.get("barcode"):
            if doc_footer["barcode"]["type"] == "code128":
                barcode = '{B' + doc_footer["barcode"]["value"]
            else:
                barcode = doc_footer["barcode"]["value"]
            prn.barcode(
                code=barcode,
                bc=doc_footer["barcode"]["type"],
                pos="OFF",
                align_ct=not width,
            )
        if doc_footer.get("qr"):
            prn.qr(doc_footer["qr"]["value"], center=not width)
    for line in doc_footer:
        prn.set(align="left", bold=False)
        name = f'{line["name"]}'
        val = f'{line["value"]:.2f}'
        if width:
            filler = " " * (width - len(name) - len(val))
            prn.textln(f'{name}{filler}{val}')
        else:
            prn.text(name)
            prn.set(align="right")
            prn.textln(val)


def print_document(printercfg, doc):
    prnt_logger.info("Configuring printer")
    prn, dummy = configure_printer(printercfg)
    prn.open()
    prnt_logger.info("Printing document")
    prnt_logger.info(doc)
    if doc["meta"]["type"] == "receipt":
        print_header(prn, doc["header"], printercfg.get("width"))
        print_content(prn, doc["content"], printercfg.get("width"))
        print_footer(prn, doc["footer"], printercfg.get("width"))
    elif doc["meta"]["type"] == "report":
        print_header(prn, doc["header"], printercfg.get("width"))
        print_report_content(prn, doc["content"], printercfg.get("width"))
        print_report_footer(prn, doc["footer"], printercfg.get("width"))
    prn.cut()
    if dummy:
        prnt_logger.info(str(prn.output))
        prn.clear()
    else:
        prn.close()
    prnt_logger.info("Document printed")
    return {"result": "OK"}
