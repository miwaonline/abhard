from flask import Flask, jsonify, request, render_template
from sysutils import logger, config
from rro_eusign import EUSign
from scaner_thread import ScanerThread, WebSocketServerThread
import signal
import sys
import base64
from http_utils import post_command, post_document

app = Flask("abhard")

rro_objects = {}
scaner_threads = {}
websocket_threads = {}
app_status = {
    "requests_served": {
        "cmd": 0,
        "doc": 0,
        "data": 0,
        "status": 0,
    }
}


# Initialize RRO objects
for rro in config["rro"]:
    rroobj = EUSign(rro["id"], rro["keyfile"], rro["keypass"])
    rro_objects[rro["id"]] = rroobj
    logger.info(f"Started RRO thread {rro['id']}")
    # thread.start()

# Initialize Scaner threads
for scaner in config["scaner"]:
    # Initialize Scaner watcher
    thread = ScanerThread(scaner["id"], scaner["device"])
    scaner_threads[scaner["id"]] = thread
    thread.start()
    logger.info(f"Started Scaner thread {scaner['id']}")
    # Initialize WebSocket listener
    wsthread = WebSocketServerThread(port=scaner["socker_port"])
    websocket_threads[scaner["id"]] = wsthread
    wsthread.start()
    logger.info("Started WebSocket server thread")


def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    for thread in scaner_threads.values():
        thread.running = False
    for thread in websocket_threads.values():
        thread.stop()
        thread.join()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


@app.route("/")
def index():
    context = {
        "version": "3.0.0.1",
        "port": config["scaner"][0]["socker_port"],
    }
    return render_template("index.html", **context)


@app.route("/api/status", methods=["GET"])
def get_status():
    app_status["requests_served"]["status"] += 1
    rro_status = {
        rro_id: euobject.rro_id for rro_id, euobject in rro_objects.items()
    }
    scaner_status = {
        scaner_id: thread.is_alive()
        for scaner_id, thread in scaner_threads.items()
    }
    websocket_status = {
        scaner_id: thread.is_alive()
        for scaner_id, thread in websocket_threads.items()
    }
    return jsonify(
        {
            "rro_status": rro_status,
            "scaner_status": scaner_status,
            "websocket_status": websocket_status,
            "requests_served": app_status["requests_served"],
        }
    )


@app.route("/api/list", methods=["GET"])
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
            "url": "api/rro/cmd/{id}/Check/{fn}/{docid}",
            "name": "Check",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/Documents/{fn}/{docid}",
            "name": "Documents",
            "type": "get",
        },
        {
            "url": "api/rro/cmd/{id}/ZRep/{fn}/{docid}",
            "name": "ZReport",
            "type": "get",
        },
        {
            "url": "api/rro/doc/{id}/",
            "name": "EUSign XML document",
            "type": "post",
        },
    )
    return jsonify(result)


@app.route(
    "/api/rro/cmd/<int:rro_id>/<string:cmdname>/",
    defaults={"regfiscalnum": -1, "docfiscalnum": -1},
    methods=["GET"],
)
@app.route(
    "/api/rro/cmd/<int:rro_id>/<string:cmdname>/<int:regfiscalnum>/",
    defaults={"docfiscalnum": -1},
    methods=["GET"],
)
@app.route(
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
                    "b64message": str(
                        base64.b64encode(bytes("ПРРО не знайдено", "utf-8"))
                    ),
                }
            ),
            404,
        )
    res, status = post_command(rroobj, cmdname, regfiscalnum, docfiscalnum)
    return jsonify(res), status


@app.route(
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
                    "b64message": str(
                        base64.b64encode(bytes("ПРРО не знайдено", "utf-8"))
                    ),
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
                    "b64message": str(
                        base64.b64encode(bytes("XML не передано", "utf-8"))
                    ),
                }
            ),
            400,
        )
    xmlcontent = base64.b64decode(request.json["xmlcontent"]).decode("utf-8")
    ordernum = xmlcontent.split("<ORDERNUM>")[1].split("</ORDERNUM>")[0]
    logger.info(f"Posting document {ordernum}")
    res, status = post_document(rroobj, xmlcontent)
    return jsonify(res), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config["webservice"]["port"])
