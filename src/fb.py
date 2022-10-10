import fdb

class fb:
    "Provides Firebird database interface"
    def __init__(self, dbhost, dbfile, dbuser, dbpass, dbport = 3050):
        self.con = fdb.connect(
            host = dbhost, database = dbfile,
            user = dbuser, password = dbpass, 
            charset = 'UTF8', port = dbport
        )

    def selectSQL(self, query, params=([])):
        "Select data from db"
        customTPB = fdb.bs([fdb.isc_tpb_version3,
                            fdb.isc_tpb_read,
                            fdb.isc_tpb_wait,
                            fdb.isc_tpb_read_committed,
                            fdb.isc_tpb_rec_version])
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
        self.con.begin(tpb = customTPB)
        cur = self.con.cursor()
        try:
            result = (-1, 'Unprocessed')
            cur.execute(query, params)
        except fdb.ProgrammingError as a:
            cur.close()
            self.con.rollback()
            result = (-2, str(a))
        except fdb.DataError as e:
            cur.close()
            self.con.rollback()
            result = (-3, str(e))
        except fdb.DatabaseError as a:
            cur.close()
            self.con.rollback()
            if 'ERROR_DYNAMIC' in str(a):
                b = str(a).split("\\n- ")
                result = (-4, b[4])
            else:
                result = (-5, str(a))
        except fdb.Error as e:
            cur.close()
            self.con.rollback()
            result = (-6, str(e))
        except:
            raise
        else:
            cur.close()
            self.con.commit()
            result = (0, 'Success')
        finally:
            return result

