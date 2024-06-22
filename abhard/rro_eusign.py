from sysutils import logger
import pathlib
import EUSignCP
import errno
import os


class EUSign:
    pIface = None

    def init_lib(self):
        if EUSign.pIface is not None:
            return
        # Load crypto lib
        try:
            EUSignCP.EULoad()
            EUSign.pIface = EUSignCP.EUGetInterface()
            EUSign.pIface.Initialize()
        except Exception:
            logger.warning("EUSignCP initialisation failed.")
            EUSignCP.EUUnload()
            exit(1)
        dSettings = {}
        EUSign.pIface.GetFileStoreSettings(dSettings)
        path = pathlib.Path(__file__).parent.absolute().parent
        dSettings["szPath"] = f"{path}/cert"
        if len(dSettings["szPath"]) == 0:
            logger.info("Crypto settings initialisation failed.")
            EUSign.pIface.Finalize()
            EUSignCP.EUUnload()
            exit(2)
        EUSign.pIface.SetFileStoreSettings(dSettings)
        logger.info(
            "Crypto library Initialised; certificates are loaded "
            f"from {dSettings['szPath']}"
        )

    def init_certificate(self, keyfile, password):
        try:
            logger.info(f'Reading {keyfile}')
            if not pathlib.Path(keyfile).is_file():
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), keyfile
                )
            ownerinfo = {}
            if not EUSign.pIface.IsPrivateKeyReaded():
                EUSign.pIface.ReadPrivateKeyFile(
                    keyfile, password, ownerinfo
                )
                logger.info("Certificate loaded successfully")
        except Exception as e:
            logger.info("Certificate reading failed: " + str(e))
            EUSign.pIface.Finalize()
            EUSignCP.EUUnload()
            raise

    def sign_request(self, xmlstr):
        s = bytes(xmlstr, "windows-1251")
        signedData = []
        EUSign.pIface.SignDataInternal(True, s, len(s), None, signedData)
        payload = signedData[0]
        checkedData = []
        EUSign.pIface.VerifyDataInternal(
            None, payload, len(payload), checkedData, None
        )
        return payload

    def __init__(self, rro_id, keyfile, password):
        self.rro_id = rro_id
        self.init_lib()
        self.init_certificate(keyfile, password)
