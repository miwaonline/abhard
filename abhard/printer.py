from sysutils import config, prnt_logger
import json
from escpos import printer
from pathlib import Path


def print_document(printer_name, doc):
    return print_dummy(doc)
    for printer in config["printer"]:
        if printer["name"] == printer_name and printer["type"] == "textfile":
            result = print_textfile(
                doc,
                Path(printer["path"] / "doc.json"),
                printer.get("width", 40),
            )
            prnt_logger.info(f"Printed document to {printer_name}")
    return result


def print_textfile(doc, filename, width):
    with open(filename, "w") as f:
        f.write(json.dumps(doc, indent=4))
    return 'OK'


def print_dummy(doc):
    p = printer.Dummy()
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
    with open("dummy.txt", "w") as f:
        f.write(str(p.output))
    return "OK"
