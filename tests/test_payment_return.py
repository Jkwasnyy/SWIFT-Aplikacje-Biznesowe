import unittest
from unittest.mock import patch

from app.services.return_service import handle_payment_return


RETURN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>RETURN-MSG-1003</MsgId>
      <CreDtTm>2026-06-09T12:00:00Z</CreDtTm>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>RETURN-INST-1003</InstrId>
        <UETR>33333333-3333-4333-8333-333333333333</UETR>
      </PmtId>
      <IntrBkSttlmAmt Ccy="GBP">30.00</IntrBkSttlmAmt>
      <RmtInf>
        <Ustrd>Zwrot</Ustrd>
      </RmtInf>
      <ReturnInf>
        <Rsn>receiver_account_closed</Rsn>
      </ReturnInf>
      <DbtrAgt>
        <FinInstnId>
          <BICFI>UKBKGB01XXX</BICFI>
        </FinInstnId>
      </DbtrAgt>
      <CdtrAgt>
        <FinInstnId>
          <BICFI>PLBKPL01XXX</BICFI>
        </FinInstnId>
      </CdtrAgt>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""


class PaymentReturnTestCase(unittest.TestCase):
    @patch("app.services.return_service.forward_message", return_value=(202, '{"status":"return_received"}'))
    def test_return_forwarded_to_original_sender(self, forward_mock):
        result, status = handle_payment_return(
            RETURN_XML,
            headers={"X-SWIFT-Message-Type": "RETURN"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "return_forwarded")
        self.assertEqual(result["original_sender_bic"], "PLBKPL01XXX")
        self.assertEqual(result["returning_bank_bic"], "UKBKGB01XXX")
        forward_mock.assert_called_once()
        args, kwargs = forward_mock.call_args
        self.assertIn("3001", args[0])
        self.assertEqual(kwargs["headers"]["X-SWIFT-Message-Type"], "RETURN")

    def test_dashboard_marks_returned_status(self):
        from app.api.ui import _build_dashboard_state

        log_lines = "\n".join(
            [
                "2026-06-09T12:00:00 [INFO] - [RECEIVED] MSG=MSG-1 UETR=33333333-3333-4333-8333-333333333333 SENDER=PLBKPL01XXX AMOUNT=10.00 CURRENCY=GBP CHRG=SHAR",
                "2026-06-09T12:00:01 [INFO] - [COMPLETED] MSG=MSG-1 UETR=33333333-3333-4333-8333-333333333333 BANK=Bank UK 1 STATUS=completed",
                "2026-06-09T12:00:02 [INFO] - [RETURN_FORWARDED] UETR=33333333-3333-4333-8333-333333333333 TO=PLBKPL01XXX REASON=receiver_account_closed STATUS=202 RESP=ok",
            ]
        )

        with patch("app.api.ui._load_log_lines", return_value=log_lines.splitlines()):
            dashboard = _build_dashboard_state()

        completed = dashboard["completed"]
        item = next(row for row in completed if row["uetr"] == "33333333-3333-4333-8333-333333333333")
        self.assertEqual(item["status"], "returned")

    def test_return_requires_zwrot_marker(self):
        invalid_xml = RETURN_XML.replace("<Ustrd>Zwrot</Ustrd>", "<Ustrd>Payment</Ustrd>")
        result, status = handle_payment_return(invalid_xml, headers={})

        self.assertEqual(status, 422)
        self.assertIn("Zwrot", result["error"])


if __name__ == "__main__":
    unittest.main()
