# Registrar of Accounting Oprations API
import cherrypy
import fb
import config
import xml.etree.ElementTree as ET
import uuid
import datetime
import requests
import gzip
import pytz
import EUSignCP
import pathlib # to get current path
import base64 # to bypass issue with Ukrainian messages
import simplejson as json # otherwise we have decimal encoding errors in win
import errno # to raise FileNotFound properly
import os    # to raise FileNotFound properly

# Initialisation tasks for the module
baseurl='http://fs.tax.gov.ua:8609/fs'
docsuburl='/doc'
cmdsuburl='/cmd'
# Initialise single db connection
fbclient = fb.fb(config.full['database']['host'],
    config.full['database']['name'], 
    config.full['database']['user'],
    config.full['database']['pass'])
cherrypy.log("Database connection initialised")
# Load crypto lib
EUSignCP.EULoad()
pIface = EUSignCP.EUGetInterface()
try:
    pIface.Initialize()
except Exception as e:
    cherrypy.log ("EUSignCP initialise failed"  + str(e))
    EUSignCP.EUUnload()
    exit(1)
dSettings = {}
pIface.GetFileStoreSettings(dSettings)
path = pathlib.Path(__file__).parent.absolute().parent
dSettings["szPath"] = f'{path}/cert'
if len(dSettings["szPath"]) == 0:
    cherrypy.log("Error crypto settings initialise")
    pIface.Finalize()
    EUSignCP.EUUnload()
    exit(2)
cherrypy.log(f"Crypto library Initialised; certificates are loaded from {dSettings['szPath']}")

if 'eusign' in config.full['rro']:
    dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == '1'), None)
else:
    dev = None
if dev is not None:
    try:
        cherrypy.log(f'Reading {dev["keyfile"]}')
        if not pathlib.Path(dev['keyfile']).is_file():
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), dev["keyfile"])
        ownerinfo = {}
        if not pIface.IsPrivateKeyReaded():
            pIface.ReadPrivateKeyFile(dev['keyfile'], dev['keypass'], ownerinfo)
            cherrypy.log('Certificate loaded successfully')
    except Exception as e:
        cherrypy.log ("Certificate reading failed: "  + str(e))
        pIface.Finalize()
        EUSignCP.EUUnload()
        exit(3)

@cherrypy.expose()
class Shift:
    def GET(self, rroid):
        '''
        Get current/last shift status
        '''
        # check shift status online
        # compare with database
        return { 'result': 'OK' }

    def POST(self, rroid):
        '''
        Start a new shift
        '''
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            cashier = input_json["cashier"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # work with db
            query = 'EXECUTE procedure rro_newshift(?, ?)'
            r = fbclient.execSQL(query, [rroid, cashier])
            query = 'SELECT r.ID, r.LOCALNUM, r.TIN, r.IPN, r.ORGNM, \
                r.POINTNM, r.POINTADDR, r.CASHREGISTERNUM FROM R_RRO r \
                where r.ID = ?'
            rrodb = fbclient.selectSQLmap(query, [rroid])[0]

            query = 'SELECT id, ordertaxnum_start from rro_shifts \
                where rro_id = ? and shift_end is null'
            shift_id, localnum = fbclient.selectSQL(query, [rroid])[0]

            query = 'select id from rro_docs where rro_id = ? and shift_id = ? and doc_type = 100'
            rrodoc = fbclient.selectSQL(query, [rroid, shift_id])[0][0]
            # prepare XML
            check = ET.Element('CHECK', 
                **{'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'}, 
                **{'xsi:noNamespaceSchemaLocation': 'check01.xsd'})
            head = ET.SubElement(check, 'CHECKHEAD')
            ET.SubElement(head, 'DOCTYPE').text = '100'
            ET.SubElement(head, 'UID').text = str(uuid.uuid4()).upper()
            ET.SubElement(head, 'TIN').text = rrodb['TIN']
            if (rrodb['IPN'] is not None) and (len(rrodb['IPN']) > 1):
                ET.SubElement(head, 'IPN').text = rrodb['IPN']
            ET.SubElement(head, 'ORGNM').text = rrodb['ORGNM']
            ET.SubElement(head, 'POINTNM').text = rrodb['POINTNM']
            ET.SubElement(head, 'POINTADDR').text = rrodb['POINTADDR']
            ET.SubElement(head, 'ORDERDATE').text = now.strftime('%d%m%Y')
            ET.SubElement(head, 'ORDERTIME').text = now.strftime('%H%M%S')
            ET.SubElement(head, 'ORDERNUM').text = str(localnum)
            ET.SubElement(head, 'CASHDESKNUM').text = rrodb['LOCALNUM']
            ET.SubElement(head, 'CASHREGISTERNUM').text = rrodb['CASHREGISTERNUM']
            ET.SubElement(head, 'CASHIER').text = cashier
            ET.SubElement(head, 'VER').text = '1'
            if test_mode:
                ET.SubElement(head, 'TESTING').text = 'true'
            tree = ET.ElementTree(check)
            #tree.write(f'check-{localnum}.xml', encoding="windows-1251")
            # sign the file
            xmlstr = ET.tostring(check, encoding="windows-1251", method='xml')
            xmlenc = ET.tostring(check, encoding="unicode", method='xml')
            xmlenc = '<?xml version="1.0" encoding="windows-1251"?>' + xmlenc
            signedData = []
            pIface.SignDataInternal(True, xmlstr, len(xmlstr), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                receiptstr = start + ticket + stop
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? where id = ?'
                r = fbclient.execSQL(query, [xmlenc, receiptstr, ordertaxnum, rrodoc])
                query = 'UPDATE rro_shifts set shift_start = ? where id = ?'
                r = fbclient.execSQL(query, [now, shift_id])
                res['result'] = 'OK'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['message'] = 'Відповідь сервера збережено'
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                query = 'UPDATE rro_docs set doc_status = 2 where id = ?'
                rrodb = fbclient.execSQL(query, [rrodoc])
                res['result'] = 'Error'
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['message'] = response.text
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }
    
    def PUT(self, rroid):
        '''
        Close current shift
        '''
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            shift_id = input_json["shift_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            # work with db
            query = 'UPDATE or INSERT into rro_docs(rro_id, shift_id, doc_type) \
                values(?, ?, ?) matching(rro_id, shift_id, doc_type)'
            r = fbclient.execSQL(query, [rroid, shift_id, 101])
            query = 'SELECT r.ID, r.LOCALNUM, r.TIN, r.IPN, r.ORGNM, \
                r.POINTNM, r.POINTADDR, r.CASHREGISTERNUM FROM R_RRO r \
                where r.ID = ?'
            rrodb = fbclient.selectSQLmap(query, [rroid])[0]
            query = 'select localnum from rro_docs where rro_id = ? and shift_id = ? and doc_type = ?'
            localnum = fbclient.selectSQL(query, [rroid, shift_id, 101])[0][0]
            query = 'select cashier from rro_shifts where rro_id = ? and id = ?'
            cashier = fbclient.selectSQL(query, [rroid, shift_id])[0][0]
            query = 'select id, localnum from rro_docs where rro_id = ? and shift_id = ? and doc_type = 101'
            rrodoc,rroloc = fbclient.selectSQL(query, [rroid, shift_id])[0]
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # prepare XML
            check = ET.Element('CHECK', 
                **{'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'}, 
                **{'xsi:noNamespaceSchemaLocation': 'check01.xsd'})
            head = ET.SubElement(check, 'CHECKHEAD')
            ET.SubElement(head, 'DOCTYPE').text = '101'
            ET.SubElement(head, 'UID').text = str(uuid.uuid4()).upper()
            ET.SubElement(head, 'TIN').text = rrodb['TIN']
            if (rrodb['IPN'] is not None) and (len(rrodb['IPN']) > 1):
                ET.SubElement(head, 'IPN').text = rrodb['IPN']
            ET.SubElement(head, 'ORGNM').text = rrodb['ORGNM']
            ET.SubElement(head, 'POINTNM').text = rrodb['POINTNM']
            ET.SubElement(head, 'POINTADDR').text = rrodb['POINTADDR']
            ET.SubElement(head, 'ORDERDATE').text = now.strftime('%d%m%Y')
            ET.SubElement(head, 'ORDERTIME').text = now.strftime('%H%M%S')
            ET.SubElement(head, 'ORDERNUM').text = str(localnum)
            ET.SubElement(head, 'CASHDESKNUM').text = rrodb['LOCALNUM']
            ET.SubElement(head, 'CASHREGISTERNUM').text = rrodb['CASHREGISTERNUM']
            ET.SubElement(head, 'CASHIER').text = cashier
            ET.SubElement(head, 'VER').text = '1'
            if test_mode:
                ET.SubElement(head, 'TESTING').text = 'true'
            tree = ET.ElementTree(check)
            #tree.write(f'shiftclose-{localnum}.xml', encoding="windows-1251")
            # sign the file
            xmlstr = ET.tostring(check, encoding="windows-1251", method='xml')
            xmlenc = ET.tostring(check, encoding="unicode", method='xml')
            xmlenc = '<?xml version="1.0" encoding="windows-1251"?>' + xmlenc
            signedData = []
            pIface.SignDataInternal(True, xmlstr, len(xmlstr), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                receiptstr = start + ticket + stop
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? where id = ?'
                r = fbclient.execSQL(query, [xmlenc, receiptstr, ordertaxnum, rrodoc])
                query = 'UPDATE rro_shifts set ordertaxnum_end = ?, shift_end = ? where id = ?'
                r = fbclient.execSQL(query, [rroloc, now, shift_id])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                query = 'UPDATE rro_docs set doc_status = 2 where id = ?'
                rrodb = fbclient.execSQL(query, [rrodoc])
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }


@cherrypy.expose()
class ZReport:
    def GET(self, rroid, shift_id):
        '''
        cherrypy.log ZReport
        '''
        try:
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            query = 'SELECT OUT FROM RRO_ZREPORT(?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [shift_id, rroid, 1])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            cherrypy.log(xmlstr)
            return {
                'result': 'OK', 
                'message': xmlstr,
                'b64message': base64.b64encode(bytes(str(xmlstr), 'utf-8'))
                }
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

    def POST(self, rroid):
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            shift_id = input_json["shift_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            # work with db
            query = 'UPDATE or INSERT into rro_docs(rro_id, shift_id, doc_type, doc_subtype, doc_timestamp)\
              values(?, ?, 32768, 32768, current_timestamp) \
              matching(rro_id, shift_id, doc_type, doc_subtype)'
            fbclient.execSQL(query, [rroid, shift_id])
            query = 'SELECT OUT FROM RRO_ZREPORT(?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [shift_id, rroid, test_mode])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            # sign the data
            signedData = []
            pIface.SignDataInternal(True, xmlstr.encode('windows-1251'), len(xmlstr.encode('windows-1251')), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? where \
                    rro_id = ? and shift_id = ? and doc_type = 32768 and doc_subtype = 32768'
                fbclient.execSQL(query, [xmlstr, start + ticket + stop, ordertaxnum, rroid, shift_id])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                query = 'UPDATE rro_docs set doc_status = 2 where  \
                    rro_id = ? and shift_id = ? and doc_type = 32768 and doc_subtype = 32768'
                rrodb = fbclient.execSQL(query, [rroid, shift_id])
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class Cashinout:
    def POST(self, rroid):
        '''
        Send service in/out payments to the tax servers
        '''
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            shift_id = input_json["shift_id"]
            doc_id = input_json["doc_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # We update doc_timestamp here because remote server wants it to be as close to "now" as possible
            # while users sometemes fiscalise documents hours after creation which causes remote exceptions
            query = 'UPDATE rro_docs set doc_timestamp = ? where id = ?'
            rrodb = fbclient.execSQL(query, [now, doc_id])
            cherrypy.log(f'Updated rro_docs with timestamp {now}')
            cherrypy.log(f'rrodb = {rrodb}')
            query = 'SELECT OUT FROM RRO_SRVCASH(?, ?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [rroid, doc_id, shift_id, test_mode])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            cherrypy.log(f'xmlstr = {xmlstr}')
            # sign the file
            signedData = []
            pIface.SignDataInternal(True, xmlstr.encode('windows-1251'), len(xmlstr.encode('windows-1251')), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? \
                    where id = ?'
                fbclient.execSQL(query, [xmlstr, start + ticket + stop, ordertaxnum, doc_id])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                # clean database
                query = 'UPDATE rro_docs set doc_status = 2 \
                    where id = ?'
                rrodb = fbclient.execSQL(query, [doc_id])
                cherrypy.log(f'Falled back doc_id {doc_id} to rro_status 2')
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            # clean database
            query = 'UPDATE rro_docs set doc_status = 2 \
                where id = ?'
            rrodb = fbclient.execSQL(query, [doc_id])
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class Receipt:
    def GET(self, rroid, docid):
        '''
        Return the document info
        '''
        try:
            dev = next((item for item in config.full['rro']['textfile'] if item['name'] == name), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            res = fbclient.selectSQL('select number,doc_date from out_check where id = ?', [docid])
            return { 
                'result': 'OK',
                'message': { 'number' : res[0][0], 'date': res[0][1].strftime('%d/%m/%Y')
                }
            }
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

    def POST(self, rroid):
        '''
        Send the check to the tax servers
        '''
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            docid = input_json["doc_id"]
            shift_id = input_json["shift_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # We update doc_timestamp here because remote server wants it to be as close to "now" as possible
            # while users sometemes fiscalise documents hours after creation which causes remote exceptions
            query = 'UPDATE rro_docs set doc_timestamp = ? where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 0'
            rrodb = fbclient.execSQL(query, [now, rroid, shift_id, docid])
            cherrypy.log(f'Updated rro_docs with timestamp {now}')
            cherrypy.log(f'rrodb = {rrodb}')
            query = 'SELECT OUT FROM RRO_CHECK(?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [docid, rroid, test_mode])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            # cherrypy.log(f'xmlstr = {xmlstr}')
            # sign the file
            signedData = []
            pIface.SignDataInternal(True, xmlstr.encode('windows-1251'), len(xmlstr.encode('windows-1251')), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? \
                    where check_id = ? and doc_type = 0 and doc_subtype = 0'
                fbclient.execSQL(query, [xmlstr, start + ticket + stop, ordertaxnum, docid])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                # clean database
                query = 'UPDATE rro_docs set doc_status = 2 \
                    where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 0 and ordertaxnum is null'
                rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
                cherrypy.log(f'Falled back doc_id {docid} to rro_status 2')
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            # clean database
            query = 'UPDATE rro_docs set doc_status = 2 \
                where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 0 and ordertaxnum is null'
            rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class ReceiptReturn:
    def GET(self, rroid, docid):
        '''
        Return the document info
        '''
        try:
            dev = next((item for item in config.full['rro']['textfile'] if item['name'] == name), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            res = fbclient.selectSQL('select number,doc_date from out_check where id = ?', [docid])
            return { 
                'result': 'OK',
                'message': { 'number' : res[0][0], 'date': res[0][1].strftime('%d/%m/%Y')
                }
            }
        except BaseException as err:
            cherrypy.log(str(err))
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

    def POST(self, rroid):
        '''
        Send the check to the tax servers
        '''
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            docid = input_json["doc_id"]
            shift_id = input_json["shift_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # We update doc_timestamp here because remote server wants it to be as close to "now" as possible
            # while users sometemes fiscalise documents hours after creation which causes remote exceptions
            query = 'UPDATE rro_docs set doc_timestamp = ? where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 1'
            rrodb = fbclient.execSQL(query, [now, rroid, shift_id, docid])
            cherrypy.log(f'Updated rro_docs with timestamp {now}')
            cherrypy.log(f'rrodb = {rrodb}')
            query = 'SELECT OUT FROM RRO_CHECKRETURN(?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [docid, rroid, test_mode])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            # sign the file
            signedData = []
            pIface.SignDataInternal(True, xmlstr.encode('windows-1251'), len(xmlstr.encode('windows-1251')), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? \
                    where check_id = ? and doc_type = 0 and doc_subtype = 1'
                fbclient.execSQL(query, [xmlstr, start + ticket + stop, ordertaxnum, docid])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                # clean database
                query = 'UPDATE rro_docs set doc_status = 2 \
                    where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 1 and ordertaxnum is null'
                rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
                cherrypy.log(f'Falled back doc_id {docid} to rro_status 2')
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            # clean database
            query = 'UPDATE rro_docs set doc_status = 2 \
                where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 1 and ordertaxnum is null'
            rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class ReceiptCancel:
    def POST(self, rroid):
        try:
            input_json = cherrypy.request.json
            cherrypy.log(f'input_json = {input_json}')
            docid = input_json["doc_id"]
            shift_id = input_json["shift_id"]
            if 'test_mode' in input_json:
                test_mode = int(input_json["test_mode"]) == 1
            else:
                test_mode = False
            dev = next((item for item in config.full['rro']['eusign'] if item['rroid'] == rroid), None)
            if dev == None:
                msgstr = f'Помилка конфігурації: немає пристрою з ІД {rroid}'
                return {
                  'result': 'Error',
                  'message': msgstr,
                  'b64message': base64.b64encode(bytes(msgstr, 'utf-8'))
                }
            tz = pytz.timezone('Europe/Kiev')
            now = datetime.datetime.now(tz)
            # We update doc_timestamp here because remote server wants it to be as close to "now" as possible
            # while users sometemes fiscalise documents hours after creation which causes remote exceptions
            query = 'UPDATE rro_docs set doc_timestamp = ? where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 5'
            rrodb = fbclient.execSQL(query, [now, rroid, shift_id, docid])
            cherrypy.log(f'Updated rro_docs with timestamp {now}')
            cherrypy.log(f'rrodb = {rrodb}')
            query = 'SELECT OUT FROM RRO_CHECKSTORNO(?, ?, ?)'
            rrodb = fbclient.selectSQL(query, [docid, rroid, test_mode])
            xmlstr=''
            # prepare XML
            for row in rrodb:
                xmlstr += row[0]
            # sign the file
            signedData = []
            pIface.SignDataInternal(True, xmlstr.encode('windows-1251'), len(xmlstr.encode('windows-1251')), None, signedData)
            payload = signedData[0]
            checkedData=[]
            pIface.VerifyDataInternal(None, payload, len(payload), checkedData, None)
            # send XML and get response
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + docsuburl, data=gzip.compress(payload), headers=headers)
            if response.status_code == 200:
                start='<?xml'
                stop='</TICKET>'
                ticket=response.text.split(start)[1].split(stop)[0]
                ordertaxnum=ticket.split('<ORDERTAXNUM>')[1].split('</ORDERTAXNUM>')[0]
                query = 'UPDATE rro_docs set doc_xml_blob = ?, doc_receipt_blob = ?, ordertaxnum = ? \
                    where check_id = ? and doc_type = 0 and doc_subtype = 5'
                fbclient.execSQL(query, [xmlstr, start + ticket + stop, ordertaxnum, docid])
                res['result'] = 'OK'
                res['message'] = 'Відповідь сервера збережено'
                res['b64message'] = base64.b64encode(bytes('Відповідь сервера збережено', 'utf-8'))
                res['status_code'] = response.status_code
            else:
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                # clean database
                query = 'UPDATE rro_docs set doc_status = 2 \
                    where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 5 and ordertaxnum is null'
                rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
                cherrypy.log(f'Falled back doc_id {docid} to rro_status 2')
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
                res['status_code'] = response.status_code
            return res
        except BaseException as err:
            cherrypy.log(str(err))
            # clean database
            query = 'UPDATE rro_docs set doc_status = 2 \
                where rro_id = ? and shift_id = ? and check_id = ? and doc_type = 0 and doc_subtype = 5 and ordertaxnum is null'
            rrodb = fbclient.execSQL(query, [rroid, shift_id, docid])
            return {
                'result': 'Error',
                'message': str(err),
                'b64message': base64.b64encode(bytes(str(err), 'utf-8'))
                }

@cherrypy.expose()
class Command:
    def GET(self, rroid, cmdname, docfiscalnum=None):
        try:
            cherrypy.log(f'Executing command {cmdname}.')
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
            rawData = json.dumps(jsonreq).encode('utf-8')
            encData = []
            pIface.SignDataInternal(True, rawData, len(rawData), None, encData)
            payload=encData[0]
            # send JSON and get response            
            headers={'Content-type': 'application/octet-stream', 'Content-Encoding': 'gzip', 'Content-Length': str(len(payload))}
            res = {}
            response = requests.post(baseurl + cmdsuburl, data=gzip.compress(payload), headers=headers)
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
                cherrypy.log(f'Помилка {response.status_code}')
                cherrypy.log(response.text)
                # preprare error repsonse
                res['result'] = 'Error'
                res['message'] = response.text
                res['status_code'] = response.status_code
                res['b64message'] = base64.b64encode(bytes(response.text, 'utf-8'))
        except BaseException as err:
            cherrypy.log(str(err))
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

