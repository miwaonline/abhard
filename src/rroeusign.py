# Registrar of Accounting Oprations API
import cherrypy
import fb
import config
import uuid
import datetime
import sys
try:
    import zoneinfo
except ImportError:
    import pytz
import requests
import gzip
import EUSignCP
import pathlib # to get current path
import base64 # to bypass issue with Ukrainian messages
import simplejson as json # otherwise we have decimal encoding errors in win
import errno # to raise FileNotFound properly
import os    # to raise FileNotFound properly
from types import SimpleNamespace # to create response object on the flight 

# Initialise single db connection
fbclient = fb.fb(config.full['database']['host'],
    config.full['database']['name'], 
    config.full['database']['user'],
    config.full['database']['pass'])
cherrypy.log(f"Connected to the database {config.full['database']['host']}:{config.full['database']['name']}", 'ABHARD')

class EUSign:
    pIface = None

    def __init__(self):
        if EUSign.pIface is not None:
            return
        # Load crypto lib
        EUSignCP.EULoad()
        EUSign.pIface = EUSignCP.EUGetInterface()
        try:
            EUSign.pIface.Initialize()
        except Exception as e:
            cherrypy.log("EUSignCP initialise failed"  + str(e), 'ABHARD')
            EUSignCP.EUUnload()
            exit(1)
        dSettings = {}
        EUSign.pIface.GetFileStoreSettings(dSettings)
        path = pathlib.Path(__file__).parent.absolute().parent
        dSettings["szPath"] = f'{path}/cert'
        if len(dSettings["szPath"]) == 0:
            cherrypy.log("Error crypto settings initialise", 'ABHARD')
            EUSign.pIface.Finalize()
            EUSignCP.EUUnload()
            exit(2)
        EUSign.pIface.SetFileStoreSettings(dSettings)
        cherrypy.log(f"Crypto library Initialised; certificates are loaded from {dSettings['szPath']}", 'ABHARD')

        if 'eusign' in config.full['rro']:
            #dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == '1'), None)
            dev = next((item for item in config.full['rro']['eusign']), None)
        else:
            dev = None
        if dev is not None:
            try:
                cherrypy.log(f'Reading {dev["keyfile"]}', 'ABHARD')
                if not pathlib.Path(dev['keyfile']).is_file():
                    raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), dev["keyfile"])
                ownerinfo = {}
                if not EUSign.pIface.IsPrivateKeyReaded():
                    EUSign.pIface.ReadPrivateKeyFile(dev['keyfile'], dev['keypass'], ownerinfo)
                    cherrypy.log('Certificate loaded successfully', 'ABHARD')
            except Exception as e:
                cherrypy.log ("Certificate reading failed: "  + str(e), 'ABHARD')
                EUSign.pIface.Finalize()
                EUSignCP.EUUnload()
                exit(3)

    def signXMLDoc(self, xmlstr):
        s = bytes(xmlstr, 'windows-1251')
        signedData = []
        EUSign.pIface.SignDataInternal(True, s, len(s), None, signedData)
        payload = signedData[0]
        checkedData = []
        EUSign.pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
        return payload

class BaseRequest:
    def __init__(self):
        # set global vars and their defaults
        self.baseurl='http://fs.tax.gov.ua:8609/fs'
        self.docsuburl='/doc'
        self.cmdsuburl='/cmd'        
        self.headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip'}
        self.timeout = 15
        self.cashier = None
        self.shift_id = None
        self.rrodoc_id = None
        self.test_mode = False
        self.dev = None
        self.doc_type = None
        self.doc_subtype = None
        self.euiface = EUSign()

    def processInput(self, rroid, input_json):
        self.dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
        if self.dev == None:
            msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
            return {
              'result': 'Error',
              'message': msgstr,
              'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
            }
        cherrypy.log(f'input_json = {input_json}', 'ABHARD')
        self.cashier = input_json.get('cashier', None)
        self.shift_id = input_json.get('shift_id', None)
        self.doc_id = input_json.get('doc_id', None)
        self.test_mode = int(input_json.get('test_mode', 0)) == 1

    def getRrodocID(self):
        query = 'SELECT id from rro_docs where rro_id = ? and shift_id = ? and doc_type = ? and doc_subtype = ?'
        result = fbclient.selectSQL(query, [self.dev['rroid'], self.shift_id, self.doc_type, self.doc_subtype])
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def prepareXMLDoc(self):
        xmlstr='This method should be redefined in child class'
        return xmlstr

    def postData(self, payload):
        self.headers['Content-Length'] = str(len(payload))
        res = {}
        try:
            response = requests.post(self.baseurl + self.docsuburl, 
                data=gzip.compress(payload), 
                headers=self.headers,
                timeout=self.timeout)
        except requests.exceptions.RequestException as e:
            response = SimpleNamespace(status_code = 504, text = 'Хутін - пуйло.')
        finally:
            return response

    def processResponse(self, response):
        cherrypy.log(f'{response.status_code=}', 'ABHARD')
        res = dict()
        if response.status_code == 200:
            start = '<?xml'
            stop = '</TICKET>'
            ticket = response.text.split(start)[1].split(stop)[0]
            ordertaxnum = ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
            cherrypy.log(f'Document {self.rrodoc_id} got {ordertaxnum=}','ABHARD')
            receiptstr = start + ticket + stop
            query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? where id = ?'
            dbres = fbclient.execSQL(query, [self.xmldoc, receiptstr, ordertaxnum, self.rrodoc_id])
            res['result'] = 'OK'
            res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
            res['message'] = 'Відповідь сервера збережено'
            res['status_code'] = response.status_code
        else:
            cherrypy.log(f'{response.text=}', 'ABHARD')
            query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_status = 2 where id = ?'
            dbres = fbclient.execSQL(query, [self.xmldoc,self.rrodoc_id])
            res['result'] = 'Error'
            res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
            res['message'] = response.text
            res['status_code'] = response.status_code
        return res

    def getUkrainianNow(self):
        if sys.version_info < (3, 9, 0):
            return datetime.datetime.now(pytz.timezone('Europe/Kiev'))
        else:
            return datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Kyiv'))

    def POST(self, rroid):
        self.processInput(rroid, cherrypy.request.json)
        self.ukrnow = self.getUkrainianNow()
        self.rrodoc_id = self.getRrodocID()
        cherrypy.log(f'{self.rrodoc_id=}', 'ABHARD')
        self.xmldoc = self.prepareXMLDoc()
        payload = self.euiface.signXMLDoc(self.xmldoc)
        response = self.postData(payload)
        result = self.processResponse(response)
        return result

    def PUT(self, rroid):
        self.processInput(rroid, cherrypy.request.json)
        self.ukrnow = self.getUkrainianNow()
        self.rrodoc_id = self.getRrodocID()
        cherrypy.log(f'{self.rrodoc_id=}', 'ABHARD')
        self.xmldoc = self.prepareXMLDoc()
        payload = self.euiface.signXMLDoc(self.xmldoc)
        response = self.postData(payload)
        result = self.processResponse(response)
        return result

@cherrypy.expose()
class Shift(BaseRequest):

    def getRrodocID(self):
        query = 'SELECT id from rro_docs where rro_id = ? and shift_id = ? and doc_type = ? '
        result = fbclient.selectSQL(query, [self.dev['rroid'], self.shift_id, self.doc_type])
        cherrypy.log(f'Getting rrodoc_id for {self.shift_id=} and {self.doc_type=}', 'ABHARD')
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def prepareXMLDoc(self):
        query = 'SELECT id, ordertaxnum_start from rro_shifts \
            where rro_id = ? and shift_end is null'
        res = fbclient.selectSQL(query, [self.dev['rroid']])        
        if res == []:
            cherrypy.log('Creating new shift', 'ABHARD')
            query = 'INSERT into rro_shifts(rro_id, cashier, shift_start)values(?, ?, ?) returning id'
            self.shift_id = fbclient.execSQL(query, [self.dev['rroid'], self.cashier, self.ukrnow])[0]
            query = 'INSERT into rro_docs(rro_id, shift_id, doc_type, doc_timestamp) values(?, ?, ?, ?) returning LOCALNUM'
            self.localnum = fbclient.execSQL(query, [self.dev['rroid'], self.shift_id, self.doc_type, self.ukrnow])[0]
            query = 'UPDATE rro_shifts set ordertaxnum_start = ? where id = ?'
            fbclient.execSQL(query, [self.localnum, self.shift_id])
            cherrypy.log(f'{self.localnum=}, {self.shift_id=}', 'ABHARD')
        else:
            cherrypy.log('Updating existing shift', 'ABHARD')
            query = 'INSERT into rro_docs(rro_id, shift_id, doc_type, doc_timestamp) values(?, ?, ?, ?) returning LOCALNUM'
            self.localnum = fbclient.execSQL(query, [self.dev['rroid'], self.shift_id, self.doc_type, self.ukrnow])[0]
            self.shift_id = res[0][0]
            query = 'UPDATE rro_shifts set ordertaxnum_end = ?, shift_end = ? where id = ?'
            fbclient.execSQL(query, [self.localnum, self.ukrnow, self.shift_id])
            cherrypy.log(f'{self.localnum=}, {self.shift_id=}', 'ABHARD')
        query = 'SELECT OUT FROM RRO_SHIFT(?, ?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.shift_id, self.dev['rroid'], self.test_mode, self.doc_type])
        xmlstr=''
        # prepare XML
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        ''' Open new shift '''
        ''' We need it here because in this case rrodoc_id is available only after prepareXMLDoc'''
        self.doc_type = 100
        self.processInput(rroid, cherrypy.request.json)
        self.ukrnow = self.getUkrainianNow()
        self.xmldoc = self.prepareXMLDoc()
        self.rrodoc_id = self.getRrodocID()
        cherrypy.log(f'{self.rrodoc_id=}', 'ABHARD')
        payload = self.euiface.signXMLDoc(self.xmldoc)
        response = self.postData(payload)
        result = self.processResponse(response)
        return result

    def PUT(self, rroid):
        ''' Close current shift '''
        ''' We need it here because in this case rrodoc_id is available only after prepareXMLDoc'''
        self.doc_type = 101
        self.processInput(rroid, cherrypy.request.json)
        self.ukrnow = self.getUkrainianNow()
        self.xmldoc = self.prepareXMLDoc()
        self.rrodoc_id = self.getRrodocID()
        cherrypy.log(f'{self.rrodoc_id=}', 'ABHARD')
        payload = self.euiface.signXMLDoc(self.xmldoc)
        response = self.postData(payload)
        result = self.processResponse(response)
        return result

@cherrypy.expose()
class ZReport(BaseRequest):
    def __init__(self):
        super().__init__()
        self.doc_type = 32768
        self.doc_subtype = 32768

    def prepareXMLDoc(self):
        query = 'UPDATE or INSERT into rro_docs(rro_id, shift_id, doc_type, doc_subtype, doc_timestamp)\
          values(?, ?, ?, ?, ?) \
          matching(rro_id, shift_id, doc_type, doc_subtype)'
        fbclient.execSQL(query, [self.dev['rroid'], self.shift_id, self.doc_type, self.doc_subtype, self.ukrnow])
        query = 'SELECT OUT FROM RRO_ZREPORT(?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.shift_id, self.dev['rroid'], self.test_mode])
        xmlstr=''
        # prepare XML
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        ''' Print Z-report '''
        ''' We need it separatele because in this case rrodoc_id is available only after prepareXMLDoc'''
        self.processInput(rroid, cherrypy.request.json)
        self.ukrnow = self.getUkrainianNow()
        self.xmldoc = self.prepareXMLDoc()
        self.rrodoc_id = self.getRrodocID()
        cherrypy.log(f'{self.rrodoc_id=}', 'ABHARD')
        payload = self.euiface.signXMLDoc(self.xmldoc)
        response = self.postData(payload)
        result = self.processResponse(response)
        return result

@cherrypy.expose()
class Cashinout(BaseRequest):
    def __init__(self):
        super().__init__()
        self.doc_type = 0
        # 2 for in, 4 for out, but we dont actually use it here
        self.doc_subtype = 4

    def getRrodocID(self):
        # for cash we work directly with the rro_doc
        return self.doc_id

    def prepareXMLDoc(self):
        query = 'UPDATE rro_docs set doc_timestamp = ? where id = ?'
        fbclient.execSQL(query, [self.ukrnow, self.rrodoc_id])
        query = 'SELECT OUT FROM RRO_SRVCASH(?, ?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.dev['rroid'], self.doc_id, self.shift_id, self.test_mode])
        xmlstr=''
        # prepare XML
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        return super().POST(rroid)

@cherrypy.expose()
class Receipt(BaseRequest):
    def __init__(self):
        super().__init__()
        self.doc_type = 0
        self.doc_subtype = 0

    def getRrodocID(self):
        query = '''SELECT id from rro_docs 
            where rro_id = ? and shift_id = ? and check_id = ?  
            and doc_type = ? and doc_subtype = ?'''
        result = fbclient.selectSQL(query, 
            [self.dev['rroid'], self.shift_id, self.doc_id, 
            self.doc_type, self.doc_subtype])
        if len(result) > 0:
            return result[0][0]
        else:
            cherrypy.log(f'Could not find rrodoc_id for {self.shift_id=} and {self.doc_id=}')
            return None

    def prepareXMLDoc(self):
        query = 'UPDATE rro_docs set doc_timestamp = ? where id = ?'
        dbres = fbclient.execSQL(query, [self.ukrnow, self.rrodoc_id])
        query = 'SELECT OUT FROM RRO_CHECK(?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.doc_id, self.dev['rroid'], self.test_mode])
        xmlstr=''
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        ''' Post new receipt '''
        return super().POST(rroid)

@cherrypy.expose()
class ReceiptReturn(BaseRequest):
    def __init__(self):
        super().__init__()
        self.doc_type = 0
        self.doc_subtype = 1

    def getRrodocID(self):
        query = '''SELECT id from rro_docs 
            where rro_id = ? and shift_id = ? and check_id = ?  
            and doc_type = ? and doc_subtype = ?'''
        result = fbclient.selectSQL(query, 
            [self.dev['rroid'], self.shift_id, self.doc_id, 
            self.doc_type, self.doc_subtype])
        if len(result) > 0:
            return result[0][0]
        else:
            return None

    def prepareXMLDoc(self):
        query = 'UPDATE rro_docs set doc_timestamp = ? where id = ?'
        fbclient.execSQL(query, [self.ukrnow, self.rrodoc_id])
        query = 'SELECT OUT FROM RRO_CHECKRETURN(?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.doc_id, self.dev['rroid'], self.test_mode])
        xmlstr=''
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        ''' Post new receipt '''
        return super().POST(rroid)

@cherrypy.expose()
class ReceiptCancel(BaseRequest):
    def __init__(self):
        super().__init__()
        self.doc_type = 0
        self.doc_subtype = 5

    def prepareXMLDoc(self):
        query = 'UPDATE rro_docs set doc_timestamp = ? where id = ?'
        fbclient.execSQL(query, [self.ukrnow, self.rrodoc_id])
        query = 'SELECT OUT FROM RRO_CHECKSTORNO(?, ?, ?)'
        rrodb = fbclient.selectSQL(query, [self.doc_id, self.dev['rroid'], self.test_mode])
        xmlstr=''
        # prepare XML
        for row in rrodb:
            xmlstr += row[0]
        return xmlstr

    def POST(self, rroid):
        ''' Post new receipt '''
        return super().POST(rroid)

@cherrypy.expose()
class Command:
    def __init__(self):
        # set global vars and their defaults
        self.baseurl='http://fs.tax.gov.ua:8609/fs'
        self.docsuburl='/doc'
        self.cmdsuburl='/cmd'        
        self.headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip'}
        self.euiface = EUSign()

    def GET(self, rroid, cmdname, docfiscalnum=None):
        baseurl='http://fs.tax.gov.ua:8609/fs'
        docsuburl='/doc'
        cmdsuburl='/cmd'        
        headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip'}
        try:
            cherrypy.log(f'Executing command {cmdname}.', 'ABHARD')
            query = 'SELECT r.CASHREGISTERNUM FROM R_RRO r \
                where r.ID = ?'
            regfiscalnum = fbclient.selectSQL(query, [rroid])[0][0]
            # prepare json depending on the cmdname
            if cmdname == 'ServerState':
                jsonreq = { 'Command': cmdname }
            elif cmdname == 'TransactionsRegistrarState':
                jsonreq = {
                    'Command': f'{cmdname}', 'NumFiscal': f'{regfiscalnum}'
                }
            elif cmdname == 'LastShiftTotals':
                jsonreq = {
                    'Command': f'{cmdname}', 'NumFiscal': f'{regfiscalnum}'
                }
            elif cmdname == 'Check':
                jsonreq = {
                    'Command': f'{cmdname}', 'RegistrarNumFiscal': f'{regfiscalnum}',
                     'NumFiscal': f'{docfiscalnum}', 'Original': True
                }
            elif cmdname == 'Documents':
                jsonreq = {
                    'Command': cmdname, 'NumFiscal': regfiscalnum,
                    'OpenShiftFiscalNum': docfiscalnum
                }
            elif cmdname == 'Shifts':
                StartDate = datetime.datetime.now() - datetime.timedelta(hours=72) 
                StartDate = StartDate.astimezone().replace(microsecond=0).isoformat()
                StopDate = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
                jsonreq = {
                    'Command': cmdname, 'NumFiscal': regfiscalnum,
                    'From': StartDate, 
                    'To': StopDate
                }
            elif cmdname == 'ZRep':
                jsonreq = {
                    'Command': cmdname, 'RegistrarNumFiscal': f'{regfiscalnum}',
                     'NumFiscal': f'{docfiscalnum}', 'Original': 'true'
                }
            else:
                jsonreq = {}
            # encrypt request
            rawData = json.dumps(jsonreq)
            encData = []
            payload = self.euiface.signXMLDoc(rawData)
            # send JSON and get response            
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            timeout = 15
            try:
                response = requests.post(baseurl + cmdsuburl, 
                    data=gzip.compress(payload), 
                    headers=headers, 
                    timeout=timeout)
            except requests.exceptions.RequestException as e:
                response = SimpleNamespace(status_code = 504, text = 'Хутін - пуйло.')
            if response.status_code == 200:
                if cmdname == 'ZRep':
                    start='<?xml'
                    stop='</ZREP>'
                    xml=start + response.text.split(start)[1].split(stop)[0] + stop
                    jsonresp = {'status_code': response.status_code, 
                        'message': xml,
                        'b64message': base64.b64encode(bytes(str(xml), 'utf-8'))}
                    cherrypy.log(json.dumps(jsonresp))
                    return jsonresp
                elif cmdname == 'Check':
                    start='<?xml'
                    stop='</CHECK>'
                    xml=start + response.text.split(start)[1].split(stop)[0] + stop
                    return {'status_code': response.status_code, 
                        'message': xml,
                        'b64message': base64.b64encode(bytes(str(xml), 'utf-8'))}
                else:
                    cherrypy.log(response.text)
                    return response.json()
            else:
                cherrypy.log(f'Помилка {response.status_code}', 'ABHARD')
                cherrypy.log(response.text, 'ABHARD')
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['status_code'] = response.status_code
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                return res
        except BaseException as err:
            cherrypy.log(str(err), 'ABHARD')
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class Root:
    receipt = Receipt()
    receiptreturn = ReceiptReturn()
    receiptcancel = ReceiptCancel()
    cashinout = Cashinout()
    zreport = ZReport()
    shift = Shift()
    cmd = Command()

    def GET(self):
        """
        The root endpoint will be used for ping check.
        """
        msgstr = 'Програмний РРО що базується на бібліотеці EUSignCP'
        return {
            'result': 'OK',
            'message': msgstr,
            'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
        }

