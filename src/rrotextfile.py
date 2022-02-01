# Registrar of Accounting Oprations API
import cherrypy
import fb
import logging
import config

# This is to initialise single db connection for the module

fbclient = fb.fb(config.full['database']['host'],
    config.full['database']['name'], 
    config.full['database']['user'],
    config.full['database']['pass'])

def append2file(filename, message):
    with open(filename, 'a') as afile:
        afile.write(f'{message}\n')

@cherrypy.expose()
class XReport:
    def GET(self, name, reportid):
        '''
        Print XReport
        '''
        try:
            dev = next((item for item in config.full['rro']['textfile'] if item['name'] == name), None)
            if dev == None:
                return {
                  'result': 'Error',
                  'message': f'Device {name} was not found'
                }
            append2file(dev['filename'], 'Z-Report was printed successfully')
            append2file(dev['filename'], '-'*80)
            return {'result': 'OK'}
        except BaseException as err:
            return {
                'result': 'Error',
                'message': err
                }

@cherrypy.expose()
class Receipt:
    def GET(self, name, docid):
        '''
        Return the document info
        '''
        try:
            dev = next((item for item in config.full['rro']['textfile'] if item['name'] == name), None)
            if dev == None:
                return {
                  'result': 'Error',
                  'message': f'Device {name} was not found'
                }
            res = fbclient.selectSQL('select number,doc_date from out_check where id = ?', [docid])
            append2file(dev['filename'], f'Requested information for receipt id {docid}')
            append2file(dev['filename'], f'Doc number is {res[0][0]}, date: {res[0][1].strftime("%d/%m/%Y")}')
            append2file(dev['filename'], '-'*80)
            return { 
                'result': 'OK',
                'content': { 'number' : res[0][0], 'date': res[0][1].strftime('%d/%m/%Y') }
            }
        except BaseException as err:
            return {
                'result': 'Error',
                'message': err
                }

    def POST(id):
        '''
        Print the document
        '''
        logging.info(f'Publishing receipt id {docid}')
        return {
            'result': 'OK',
            'message': 'Ура!'
        }

@cherrypy.expose()
class Root:
    receipt = Receipt()
    xreport = XReport()

    def GET(self):
        """
        The root endpoint will be used for ping check.
        """
        return {
            'result': 'OK',
            'message': 'This is a debug RRO that just stores all the data in a log file'
        }

