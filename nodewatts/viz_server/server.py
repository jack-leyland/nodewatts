import flask
import os
import json
import sys
import webbrowser
from threading import Timer
from bson import json_util
from bson import ObjectId
from nodewatts.db import Database, DatabaseError
from nodewatts.error import NodewattsError
from nodewatts.config import NWConfig
from flask import render_template, request

class VizServerError(NodewattsError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

def run(port=8080, mongo_url="mongodb://localhost:27017"):
    app = flask.Flask(__name__, static_folder="../../resources/visualizer", template_folder="../../resources/visualizer", static_url_path="")
    app.config['CORS_HEADERS'] = 'Content-Type'

    @app.route("/")
    def start():
        return render_template('index.html')

    @app.route('/options', methods=['GET'])
    def options():
        res = {
            "fail": False,
            "reason": "",
            "options": [],
        }
        try:
            db = Database(mongo_url)
            db.connect()
            cursor = db.internal_client["nodewatts"]["reports"].find({},{"name":1, "_id":1})
            for doc in cursor:
                res["options"].append(json_util.dumps(doc))
            db.close_connections()
        except DatabaseError:
            res["fail"] = True
            res["reason"] = "Server database error"
            return json.dumps(res)
        else:
            return json.dumps(res)

    @app.route('/profiles', methods=['GET'])
    def get_profile():
        res = {
            "fail": False,
            "reason": "",
            "profile": {},
        }
        arg = request.args.get('profile')
        try:
            db = Database(mongo_url)
            db.connect()
            req = json.loads(arg)
            id = ObjectId(req["$oid"])
            doc = db.internal_client["nodewatts"]["reports"].find_one(id)
            res["profile"] = json_util.dumps(doc)
            db.close_connections()
        except DatabaseError:
                res["fail"] = True
                res["reason"] = "Database error"
                return json.dumps(res)
        else:
            return json.dumps(res)
    
    def open_browser():
        webbrowser.open("http://localhost:8080")
    
    Timer(1.0, open_browser).start()
    app.run(port=port)


if __name__ == '__main__':
    try: 
        with open(os.path.join(NWConfig.dirs.site_config_dir, "viz_config.json")) as f:
            conf = json.load(f)
    except OSError as e:
        raise VizServerError("Failed to load configuration file. Please run nodewatts with visualize set to true to generate the neccessary configuration to run the server as a module.")
    run(conf["port"], conf["mongo_url"])
    sys.exit(0)
