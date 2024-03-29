import os, os.path
import random
import string
from datetime import datetime
import cherrypy
import simplejson as json # otherwise we have decimal encoding errors in win
import requests # to show out API usage right on index page
import fb
import config
import rro
import rrotextfile
import rroeusign
from version import __version_info__, __version__

@cherrypy.expose()
@cherrypy.tools.json_in()
@cherrypy.tools.json_out()
class AbhardAPI(object):
    def GET(self):
        """
        The root endpoint will be used for ping check.
        """
        result = {
            'result': 'OK',
            'UTC time': str(datetime.utcnow().isoformat()),
            'local time': str(datetime.now().isoformat()),
            'version': __version__
        }
        return result

class Abhard(object):
    @cherrypy.expose
    def index(self):
        r = requests.get(url='http://localhost:8080/api')        
        return f"""
Abhard {__version__}.<br/>
Колись тут буде інструкція і статус/налаштування всіх пристроїв.<br/>
А у далекому майбутньому ще щось.<br/> 
{json.dumps(r.json(), indent=4)}"""

def main():
    conf = {
        '/': {
            'tools.encode.encoding': 'UTF-8',
            },
        '/api': {
            'tools.encode.encoding': 'UTF-8',
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json'),('Content-Encoding','utf-8')],
        }
    }

    webapp = Abhard()
    webapp.api = AbhardAPI()
    webapp.api.rro = rro.Root()
    webapp.api.rro.textfile = rrotextfile.Root()
    webapp.api.rro.eusign = rroeusign.Root()
    cherrypy.server.socket_host = '0.0.0.0'
    cherrypy.server.socket_port = config.full['webservice']['port']
    cherrypy.log(f'Launching Abhard version {__version__}', 'ABHARD')
    cherrypy.quickstart(webapp, '/', conf)

if __name__ == '__main__':
    main()
