import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from abhard.http_utils import prepare_json, gen_err_response, gen_ok_response


class TestPrepareJson(unittest.TestCase):
    def test_server_state(self):
        cmdname = "ServerState"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {"Command": cmdname}
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )

    def test_transactions_registrar_state(self):
        cmdname = "TransactionsRegistrarState"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {"Command": cmdname, "NumFiscal": str(regfiscalnum)}
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )

    def test_last_shift_totals(self):
        cmdname = "LastShiftTotals"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {"Command": cmdname, "NumFiscal": str(regfiscalnum)}
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )

    def test_check(self):
        cmdname = "Check"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {
            "Command": cmdname,
            "RegistrarNumFiscal": str(regfiscalnum),
            "NumFiscal": str(docfiscalnum),
            "Original": True,
        }
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )

    def test_documents(self):
        cmdname = "Documents"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {
            "Command": cmdname,
            "NumFiscal": str(regfiscalnum),
            "OpenShiftFiscalNum": str(docfiscalnum),
        }
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )

    def test_shifts(self):
        cmdname = "Shifts"
        regfiscalnum = 123
        StartDate = datetime.now() - timedelta(hours=72)
        StartDate = StartDate.astimezone().replace(microsecond=0).isoformat()
        StopDate = (
            datetime.now().astimezone().replace(microsecond=0).isoformat()
        )
        expected_result = {
            "Command": cmdname,
            "NumFiscal": str(regfiscalnum),
            "From": StartDate,
            "To": StopDate,
        }
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, ""), expected_result
        )

    def test_zrep(self):
        cmdname = "ZRep"
        regfiscalnum = 123
        docfiscalnum = 456
        expected_result = {
            "Command": cmdname,
            "RegistrarNumFiscal": str(regfiscalnum),
            "NumFiscal": str(docfiscalnum),
            "Original": "true",
        }
        self.assertEqual(
            prepare_json(cmdname, regfiscalnum, docfiscalnum), expected_result
        )


class TestGenResponses(unittest.TestCase):
    @patch("abhard.http_utils.logger.warning")
    def test_gen_err_responses(self, mock_warning):
        for text, status_code in [
            ("", 500),
            ("Some message", 400),
        ]:
            with self.subTest(text=text, status_code=status_code):
                expected_result = {
                    "result": "Error",
                    "message": text,
                    "status_code": status_code,
                }
                result, code = gen_err_response(text, status_code)
                self.assertEqual(result["result"], "Error")
                self.assertEqual(code, status_code)
                self.assertEqual(result, expected_result)
                mock_warning.assert_called_with(
                    f"Помилка {status_code}. {text=}"
                )

    @patch("abhard.http_utils.logger.warning")
    def test_gen_err_response(self, mock_warning):
        # Test case 1: text is None
        text = None
        status_code = 500
        expected_result = {
            "result": "Error",
            "message": "",
            "status_code": status_code,
        }
        expected_status_code = status_code
        result, status_code = gen_err_response(text, status_code)
        self.assertEqual(result, expected_result)
        self.assertEqual(status_code, expected_status_code)
        mock_warning.assert_called_with(f"Помилка {status_code}. {text=}")

        # Test case 3: status_code is negative
        text = "This is an error message"
        status_code = -1
        expected_result = {
            "result": "Error",
            "message": text,
            "status_code": -1,
        }
        expected_status_code = -1
        result, status_code = gen_err_response(text, status_code)
        self.assertEqual(result, expected_result)
        self.assertEqual(status_code, expected_status_code)
        mock_warning.assert_called_with(f"Помилка {status_code}. {text=}")

    def test_gen_ok_response_success(self):
        for text, status_code in [
            ("<?xml<TICKET>123</TICKET>", 200),
            ("<?xml<ZREP>456</ZREP>", 200),
            ("<?xml<RECEIPT>789</RECEIPT>", 200),
            ("<?xml<CHECK>ABC</CHECK>", 200),
            (
                """�
��q�m<?xml version="1.0" encoding="windows-1251"?><TICKET xmlns:xsi="http://ww\
w.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ticket01.xsd"\
><UID>CA9CA66A-7E21-418B-81C0-494BF07189E2</UID><ORDERDATE>15062024</ORDERDATE\
><ORDERTIME>035429</ORDERTIME><ORDERNUM>357</ORDERNUM><ORDERTAXNUM>2559207071<\
/ORDERTAXNUM><ERRORCODE>0</ERRORCODE><VER>1</VER></TICKET>��d0�`0�X�""",
                200,
            ),
        ]:
            with self.subTest(text=text, status_code=status_code):
                response, code = gen_ok_response(text, status_code)
                self.assertEqual(response["result"], "OK")
                self.assertEqual(code, status_code)

    def test_gen_ok_response_exception_handling(self):
        text = "<?xml<ORDERTAXNUM>XYZ</ORDERTAXNUM>"
        status_code = 200
        with self.assertLogs():
            response, code = gen_ok_response(text, status_code)
            self.assertEqual(response["result"], "Error")
            self.assertEqual(code, status_code)


if __name__ == "__main__":
    unittest.main()
