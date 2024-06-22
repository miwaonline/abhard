import requests
from urllib3.util import Retry
from requests import Session
from requests.adapters import HTTPAdapter
import datetime
import gzip
import base64
import json
from sysutils import logger, config
import string


def prepare_json(cmdname, regfiscalnum, docfiscalnum):
    if cmdname == "ServerState":
        result = {"Command": cmdname}
    elif cmdname == "TransactionsRegistrarState":
        result = {
            "Command": f"{cmdname}",
            "NumFiscal": f"{regfiscalnum}",
        }
    elif cmdname == "LastShiftTotals":
        result = {
            "Command": f"{cmdname}",
            "NumFiscal": f"{regfiscalnum}",
        }
    elif cmdname == "Check":
        result = {
            "Command": f"{cmdname}",
            "RegistrarNumFiscal": f"{regfiscalnum}",
            "NumFiscal": f"{docfiscalnum}",
            "Original": True,
        }
    elif cmdname == "Documents":
        result = {
            "Command": cmdname,
            "NumFiscal": f"{regfiscalnum}",
            "OpenShiftFiscalNum": f"{docfiscalnum}",
        }
    elif cmdname == "Shifts":
        StartDate = datetime.datetime.now() - datetime.timedelta(hours=72)
        StartDate = StartDate.astimezone().replace(microsecond=0).isoformat()
        StopDate = (
            datetime.datetime.now()
            .astimezone()
            .replace(microsecond=0)
            .isoformat()
        )
        result = {
            "Command": cmdname,
            "NumFiscal": f"{regfiscalnum}",
            "From": StartDate,
            "To": StopDate,
        }
    elif cmdname == "ZRep":
        result = {
            "Command": cmdname,
            "RegistrarNumFiscal": f"{regfiscalnum}",
            "NumFiscal": f"{docfiscalnum}",
            "Original": "true",
        }
    else:
        result = {}
    return result


def gen_err_response(text, status_code):
    logger.warning(f"Помилка {status_code}. {text=}")
    if isinstance(text, str):
        b64 = str(base64.b64encode(bytes(text, "utf-8")))
    else:
        b64 = ""
    return (
        {
            "result": "Error",
            "message": text or "",
            "status_code": status_code,
            "b64message": b64,
        },
        status_code,
    )


def gen_ok_response(text, status_code):
    plaintext = "".join(filter(lambda x: x in string.printable, text))
    start = "<?xml"
    if "<TICKET" in plaintext:
        stop = "</TICKET>"
    elif "<ZREP" in plaintext:
        stop = "</ZREP>"
    elif "<RECEIPT" in plaintext:
        stop = "</RECEIPT>"
    elif "<CHECK" in plaintext:
        stop = "</CHECK>"
    try:
        ticket = plaintext.split(start)[1].split(stop)[0]
        if "<ORDERTAXNUM" in ticket:
            otnum = ticket.split("<ORDERTAXNUM>")[1].split("</ORDERTAXNUM>")[0]
            logger.info(f"Received document {otnum=}")
        else:
            otnum = None
    except Exception as e:
        return gen_err_response(str(e), status_code)
    receiptstr = start + ticket + stop
    return {
        "result": "OK",
        "message": receiptstr,
        "b64message": str(
            base64.b64encode(bytes(receiptstr, "utf-8")).decode("utf-8")
        ),
        "ordertaxnum": otnum,
    }, status_code


def post_raw_data(rroobj, endpoint, rawData):
    try:
        signed_data = rroobj.sign_request(rawData)
        data = gzip.compress(signed_data)
    except Exception as e:
        return gen_err_response(str(e), 500)
    headers = {
        "Content-type": "application/octet-stream",
        "Content-Encoding": "gzip",
        "Content-Length": str(len(data)),
    }
    session = Session()
    retry_strategy = Retry(
        total=config["http"]["max_retries"],
        status_forcelist=[104],
        allowed_methods=["POST"],
        backoff_factor=1,
        redirect=True,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    external_api_url = f"http://fs.tax.gov.ua:8609/fs{endpoint}"
    try:
        response = session.post(
            external_api_url,
            data=data,
            headers=headers,
            timeout=(
                config["http"]["connect_timeout"],
                config["http"]["total_timeout"],
            ),
        )
        logger.info(f"Response code: {response.status_code}.")
        if response.status_code == 200:
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.json(), response.status_code
            else:
                return gen_ok_response(response.text, response.status_code)
        else:
            logger.warning(response.text)
            return gen_err_response(response.text, response.status_code)
    except requests.exceptions.Timeout:
        logger.warning("Timeout.")
        return gen_err_response("Хутін - пуйло!", 504)
    except requests.exceptions.RequestException as e:
        logger.warning("Request exception:" + str(e))
        return gen_err_response(str(e), 500)


def post_command(rroobj, cmdname, regfiscalnum, docfiscalnum):
    rawData = json.dumps(prepare_json(cmdname, regfiscalnum, docfiscalnum))
    return post_raw_data(rroobj, "/cmd", rawData)


def post_document(rroobj, docstring):
    rawData = docstring
    return post_raw_data(rroobj, "/doc", rawData)
