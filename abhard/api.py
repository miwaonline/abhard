from flask import Blueprint, jsonify, request, render_template
from sysutils import main_logger, config, version
from http_utils import post_command, post_document
from printer import print_document
import base64
import json


api = Blueprint("api", __name__)
rro_objects = {}
scaner_threads = {}
tcpsocket_threads = {}
app_status = {
    "requests_served": {
        "cmd": 0,
        "doc": 0,
        "data": 0,
        "status": 0,
        "printer": 0,
    }
}


@api.route("/")
def index():
    context = {
        "version": version,
        "requests_served": app_status["requests_served"],
        "rro_status": {
            rro_id: euobject.rro_id for rro_id, euobject in rro_objects.items()
        },
        "scaner_status": {
            scaner_id: thread.is_alive()
            for scaner_id, thread in scaner_threads.items()
        },
        "tcpsocket_status": {
            scaner_id: thread.is_alive()
            for scaner_id, thread in tcpsocket_threads.items()
        },
    }
    return render_template("index.html", **context)


@api.route("/api/status", methods=["GET"])
def get_status():
    app_status["requests_served"]["status"] += 1
    rro_status = {
        rro_id: euobject.rro_id for rro_id, euobject in rro_objects.items()
    }
    scaner_status = {
        scaner_id: thread.is_alive()
        for scaner_id, thread in scaner_threads.items()
    }
    tcpsocket_status = {
        scaner_id: thread.is_alive()
        for scaner_id, thread in tcpsocket_threads.items()
    }
    return jsonify(
        {
            "rro_status": rro_status,
            "scaner_status": scaner_status,
            "tcpsocket_status": tcpsocket_status,
            "requests_served": app_status["requests_served"],
            "version": version,
        }
    )


@api.route("/api/list", methods=["GET"])
def get_api_list():
    result = (
        {
            "url": "api/rro/cmd/{id}/LastShiftTotals/{fn}/",
            "name": "LastShiftTotals",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/ServerState/{fn}/",
            "name": "ServerState",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/TransactionsRegistrarState/{fn}/",
            "name": "TransactionsRegistrarState",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/Check/{fn}/{docid}/",
            "name": "Check",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/Documents/{fn}/{docid}/",
            "name": "Documents",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/ZRep/{fn}/{docid}/",
            "name": "ZReport",
            "type": "get",
        },
        {
            "url": "api/status/",
            "name": "Status",
            "type": "get",
        },
        {
            "url": "api/rro/doc/{id}/",
            "name": "EUSign XML document",
            "type": "post",
        },
    )
    return jsonify(result)


@api.route("/api/scaner/<string:scaner_name>/", methods=["GET"])
def get_scaner(scaner_name):
    if not isinstance(scaner_name, str):
        return jsonify(
            {
                "result": "error",
                "message": "Scaner name must be a string",
                "status_code": 400,
            }
        )
    app_status["requests_served"]["data"] += 1
    for scaner in config["scaner"]:
        if scaner["name"] == scaner_name:
            return jsonify(
                {
                    "result": "ok",
                    "host": scaner.get("socket_host", "127.0.0.1"),
                    "port": scaner["socket_port"],
                }
            )
    return jsonify(
        {"result": "error", "message": "Scaner not found", "status_code": 404}
    )


@api.route(
    "/api/rro/cmd/<int:rro_id>/<string:cmdname>/",
    defaults={"regfiscalnum": -1, "docfiscalnum": -1},
    methods=["GET"],
)
@api.route(
    "/api/rro/cmd/<int:rro_id>/<string:cmdname>/<int:regfiscalnum>/",
    defaults={"docfiscalnum": -1},
    methods=["GET"],
)
@api.route(
    (
        "/api/rro/cmd/<int:rro_id>/<string:cmdname>/<int:regfiscalnum>/"
        "<int:docfiscalnum>/"
    ),
    methods=["GET"],
)
def rro_cmd(rro_id, cmdname, regfiscalnum, docfiscalnum):
    app_status["requests_served"]["cmd"] += 1
    rroobj = rro_objects.get(rro_id)
    if not rroobj:
        return (
            jsonify(
                {
                    "result": "error",
                    "message": "ПРРО не знайдено",
                    "status_code": 404,
                }
            ),
            404,
        )
    res, status = post_command(rroobj, cmdname, regfiscalnum, docfiscalnum)
    return jsonify(res), status


@api.route(
    "/api/rro/doc/<int:rro_id>/",
    methods=["POST"],
)
def rro_doc(rro_id):
    app_status["requests_served"]["doc"] += 1
    rroobj = rro_objects.get(rro_id)
    if not rroobj:
        return (
            jsonify(
                {
                    "result": "error",
                    "message": "ПРРО не знайдено",
                    "status_code": 404,
                }
            ),
            404,
        )
    if not request.json.get("xmlcontent", None):
        return (
            jsonify(
                {
                    "result": "error",
                    "message": "XML не передано",
                    "status_code": 400,
                }
            ),
            400,
        )
    xmlcontent = base64.b64decode(request.json["xmlcontent"]).decode("utf-8")
    ordernum = xmlcontent.split("<ORDERNUM>")[1].split("</ORDERNUM>")[0]
    main_logger.info(f"Posting document {ordernum}")
    res, status = post_document(rroobj, xmlcontent)
    return jsonify(res), status


@api.route(
    "/api/printer/<string:printer_name>/",
    methods=["POST"],
)
def print_doc(printer_name):
    app_status["requests_served"]["printer"] += 1
    main_logger.info(f"Printing document to {printer_name}")
    for printer in config["printer"]:
        if printer["name"] == printer_name:
            doc = base64.b64decode(request.json["content"]).decode("utf-8")
            jsondoc = json.loads(doc)
            res = print_document(printer, jsondoc)
            return jsonify(res), 200
    return jsonify({"result": "error", "message": "Printer not found"}), 404
