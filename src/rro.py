# Registrar of Accounting Oprations API
import cherrypy
import config
import base64

@cherrypy.expose()
#@cherrypy.tools.json_out()
class Root:
    def GET(self):
        '''
The root endpoint is used for config check - it will list all the registered RRO devices
'''
        try:
            reg = []
            for key in config.full:
                if key == 'rro':
                    for rrotype in config.full[key]:
                        for device in config.full[key][rrotype]:
                            reg.append(device['name'])
            res = {}
            res['result'] = 'OK'
            res['availabletypes'] = ['logfile', 'soft']
            res['registerednames'] = reg
            res['b64message'] = base64.b64encode(bytes('Тестове повідомлення', 'utf-8'))
            return res
        except BaseException as err:
            return {
                'result': 'Error',
                'message': err
                }
