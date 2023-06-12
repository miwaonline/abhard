import fdb
import cherrypy

class fb:
    "Provides Firebird database interface"
    def __init__(self, dbhost, dbfile, dbuser, dbpass, dbport = 3050):
        self.dbhost = dbhost
        self.dbport = dbport
        self.dbfile = dbfile
        self.dbuser = dbuser
        self.dbpass = dbpass
        self.con = fdb.connect(
            host = self.dbhost, database = self.dbfile,
            user = self.dbuser, password = self.dbpass, 
            charset = 'UTF8', port = self.dbport
        )

    def reconnect(self):
        cherrypy.log('Commenced reconnection')
        delay = 1
        while True:
            if delay < 30:
                delay += 1
            try:
                self.con = fdb.connect(
                    host = self.dbhost, database = self.dbfile,
                    user = self.dbuser, password = self.dbpass, 
                    charset = 'UTF8', port = self.dbport
                )
                cherrypy.log('Connect reestablished.')
            except fdb.fbcore.DatabaseError as dberr:
                cherrypy.log('... database unavailable; keep trying')
                time.sleep(delay)
                continue
            break

    def selectSQL(self, query, params=([])):
        "Select data from db"
        customTPB = fdb.bs([fdb.isc_tpb_version3,
                            fdb.isc_tpb_read,
                            fdb.isc_tpb_wait,
                            fdb.isc_tpb_read_committed,
                            fdb.isc_tpb_rec_version])
        try:
            self.con.begin(tpb = customTPB)
            cur = self.con.cursor()
            cur.execute(query, params)
        except fdb.fbcore.DatabaseError as dberr:
            if dberr.args[2] == 335544726:
                cherrypy.log('DB connection is closed; reconnecting')
                self.con.close()
                self.reconnect()
            self.con.begin(tpb = customTPB)
            cur = self.con.cursor()
            cur.execute(query, params)
        result = cur.fetchall()
        cur.close()
        self.con.commit()
        return result

    def selectSQLmap(self, query, params=([])):
        customTPB = fdb.bs([fdb.isc_tpb_version3,
                            fdb.isc_tpb_read,
                            fdb.isc_tpb_wait,
                            fdb.isc_tpb_read_committed,
                            fdb.isc_tpb_rec_version])
        try:
            self.con.begin(tpb = customTPB)
            cur = self.con.cursor()
            cur.execute(query, params)
        except fdb.fbcore.DatabaseError as dberr:
            if dberr.args[2] == 335544726:
                cherrypy.log('DB connection is closed; reconnecting')
                self.con.close()
                self.reconnect()
            self.con.begin(tpb = customTPB)
            cur = self.con.cursor()
            cur.execute(query, params)
        result = cur.fetchallmap()
        cur.close()
        self.con.commit()
        return result

    def getBlob(self, query, blobfield):
        "Select one blob from database"
        customTPB = fdb.bs([fdb.isc_tpb_version3,
                            fdb.isc_tpb_read,
                            fdb.isc_tpb_wait,
                            fdb.isc_tpb_read_committed,
                            fdb.isc_tpb_rec_version])
        self.con.begin(tpb = customTPB)
        cur = self.con.cursor()
        blobquery = cur.prep(query)
        try:
            cur.execute(blobquery)
            blobquery.set_stream_blob(blobfield)
            blobraw = cur.fetchone()[0] #added [0]

            if type(blobraw) is str:
                result = blobraw
            elif type(blobraw) is fdb.fbcore.BlobReader:
                result = blobraw.read()
                blobraw.close()
            elif type(blobraw) is bytes:
                result = blobraw
            else:
                result = (None, 'Unknown type ' + str(type(blobraw)), query)
            
            cur.close()
            self.con.commit()
        except fdb.ProgrammingError(errText):
            cur.close()
            self.con.rollback()
            result = (-1, errText, query)
        except:
            cur.close()
            self.con.rollback()
            result = (None, 'Unknown error', query)
        finally:
            return result

    def execSQL(self, query, params=([])):
        customTPB = fdb.bs([fdb.isc_tpb_version3,
                            fdb.isc_tpb_write,
                            fdb.isc_tpb_read_committed,
                            fdb.isc_tpb_rec_version])
        try:
            self.con.begin(tpb = customTPB)
            cur = self.con.cursor()
            result = (-1, 'Unprocessed')
            cur.execute(query, params)
            #looks like this line breaks everything
            result = cur.fetchone()
        except fdb.ProgrammingError as a:
            cur.close()
            self.con.rollback()
            result = (-2, str(a))
        except fdb.DataError as e:
            cur.close()
            self.con.rollback()
            result = (-3, str(e))
        except fdb.DatabaseError as a:
            if (len(a.args) > 1) and (a.args[2] == 335544726):
                self.con.close()
                self.reconnect()
                self.con.begin(tpb = customTPB)
                cur = self.con.cursor()
                cur.execute(query, params)
                # the next 3 lines are not perferct; they assume the query went fine
                # but I dont have a nice idea how to refactor the whole method atm
                cur.close()
                self.con.commit()
                result = (0, 'Success')
            elif 'ERROR_DYNAMIC' in str(a):
                cur.close()
                self.con.rollback()
                b = str(a).split("\\n- ")
                result = (-4, b[4])
            elif 'statement that does not produce result set' in str(a):
                cur.close()
                self.con.commit()
                result = (0, 'Success')
            else:
                cur.close()
                self.con.rollback()
                result = (-5, str(a))
        except fdb.Error as e:
            cur.close()
            self.con.rollback()
            result = (-6, str(e))
        except Exception as e:
            cur.close()
            self.con.rollback()
            result = (-7, str(e))
        else:
            cur.close()
            self.con.commit()
            if result == (-1, 'Unprocessed'):
                result = (0, 'Success')
        finally:
            return result

