import unittest
from unittest.mock import patch

from app.services.parser import parse_xml
from app.services.swift_service import handle_swift_message


# TESTOWY KOMUNIKAT PACS.008 (ISO 20022 SWIFT CBPR+)
SAMPLE_XML = """<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">

  <FIToFICstmrCdtTrf>

    <GrpHdr>
      <MsgId>MSG-1</MsgId>
      <CreDtTm>2026-05-12T09:30:00Z</CreDtTm>
    </GrpHdr>

    <CdtTrfTxInf>

      <PmtId>
        <InstrId>INST-1</InstrId>
        <UETR>8a776f2b-300b-43e2-a703-bb84c18ad518</UETR>
      </PmtId>

      <ChrgBr>SHAR</ChrgBr>

      <Dbtr>
        <Nm>Polska Spółka Importowa</Nm>
      </Dbtr>

      <DbtrAgt>
        <FinInstnId>
          <BICFI>PLBANK1XXX</BICFI>
        </FinInstnId>
      </DbtrAgt>

      <Cdtr>
        <Nm>London Trading Ltd</Nm>
      </Cdtr>

      <CdtrAgt>
        <FinInstnId>
          <BICFI>UKBANK1XXX</BICFI>
        </FinInstnId>
      </CdtrAgt>

      <IntrBkSttlmAmt Ccy="PLN">100.00</IntrBkSttlmAmt>

      <RmtInf>
        <Ustrd>Invoice INV-1</Ustrd>
      </RmtInf>

    </CdtTrfTxInf>

  </FIToFICstmrCdtTrf>

</Document>"""


class SwiftFlowTestCase(unittest.TestCase):

    # parser PACS.008 → obiekt domenowy
    def test_parse_iso20022_message(self):
        message = parse_xml(SAMPLE_XML)

        self.assertEqual(message.message_id, "MSG-1")
        self.assertEqual(message.instruction_id, "INST-1")

        self.assertEqual(message.uetr, "8a776f2b-300b-43e2-a703-bb84c18ad518")

        self.assertEqual(message.charge_bearer, "SHAR")
        self.assertEqual(message.sender_bic, "PLBANK1XXX")
        self.assertEqual(message.receiver_bic, "UKBANK1XXX")

        self.assertEqual(message.amount, "100.00")
        self.assertEqual(message.currency, "PLN")

        self.assertEqual(message.remittance_info, "Invoice INV-1")

    # routing + forwarding do banku docelowego
    @patch("app.services.swift_service.forward_message")
    def test_handle_swift_message_forwards_to_known_bank(self, forward_message_mock):

        forward_message_mock.return_value = (202, '{"status": "accepted"}')

        result, status = handle_swift_message(SAMPLE_XML)

        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "submitted")

        self.assertEqual(result["receiver_bank"], "Bank UK 1")

        self.assertEqual(result["forwarded_to"], "http://localhost:3003/receive")

        forward_message_mock.assert_called_once()

    def test_handle_swift_message_rejects_unknown_receiver(self):

        unknown_receiver_xml = SAMPLE_XML.replace("UKBANK1XXX", "ZZBANK1XXX")

        result, status = handle_swift_message(unknown_receiver_xml)

        self.assertEqual(status, 404)
        self.assertEqual(result["error"], "Bank not found")


if __name__ == "__main__":
    unittest.main()