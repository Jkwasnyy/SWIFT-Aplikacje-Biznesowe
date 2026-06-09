import unittest
from unittest.mock import patch

from app.services.parser import parse_xml
from app.services.swift_service import handle_swift_message
from app.services import inbox
from app.services.router import get_route


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

      <DbtrAcct>
        <Id>
          <IBAN>PL61109010140000071219812874</IBAN>
        </Id>
      </DbtrAcct>

      <DbtrAgt>
        <FinInstnId>
          <BICFI>PLBKPL01XXX</BICFI>
        </FinInstnId>
      </DbtrAgt>

      <Cdtr>
        <Nm>London Trading Ltd</Nm>
      </Cdtr>

      <CdtrAgt>
        <FinInstnId>
          <BICFI>UKBKGB01XXX</BICFI>
        </FinInstnId>
      </CdtrAgt>

      <CdtrAcct>
        <Id>
          <Othr>
            <Id>GB29NWBK60161331926819</Id>
          </Othr>
        </Id>
      </CdtrAcct>

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
        self.assertEqual(message.sender_bic, "PLBKPL01XXX")
        self.assertEqual(message.receiver_bic, "UKBKGB01XXX")

        self.assertEqual(message.amount, "100.00")
        # UK receiver -> GBP (waluta z banku konta docelowego, nie z XML)
        self.assertEqual(message.currency, "GBP")

        self.assertEqual(message.remittance_info, "Invoice INV-1")

    # routing + forwarding do banku docelowego
    @patch("app.services.swift_service.forward_message")
    def test_handle_swift_message_forwards_to_known_bank(self, forward_message_mock):
        # For the updated design incoming messages are stored in inbox awaiting manual send
        with patch("app.services.inbox.add_incoming") as inbox_add:
            result, status = handle_swift_message(SAMPLE_XML)

            self.assertEqual(status, 202)
            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["receiver_bank"], "Bank UK 1")
            self.assertEqual(result["route"], ["PLBKPL01XXX", "UKBKGB01XXX"])
            self.assertIn("total_fee", result["fee_breakdown"])
            inbox_add.assert_called_once()

    def test_handle_swift_message_rejects_unknown_receiver(self):

        unknown_receiver_xml = SAMPLE_XML.replace("UKBKGB01XXX", "ZZBANK1XXX")

        result, status = handle_swift_message(unknown_receiver_xml)

        self.assertEqual(status, 404)
        self.assertEqual(result["error"], "Route not found")

    def test_handle_swift_message_rejects_closed_receiver_account(self):
        closed_account_xml = SAMPLE_XML.replace(
            "GB29NWBK60161331926819",
            "GB00CLOSED0000000000000000",
        )

        result, status = handle_swift_message(closed_account_xml)

        self.assertEqual(status, 422)
        self.assertEqual(result["error"], "Receiver account closed")

    def test_weighted_route_prefers_faster_path(self):
        route = get_route("PLBKPL01XXX", "USBKUS01XXX")

        self.assertEqual(
            route,
            ["PLBKPL01XXX", "UKBKGB01XXX", "UKBKGB02XXX", "USBKUS02XXX", "USBKUS01XXX"],
        )

    def test_route_to_eu_bank(self):
        route = get_route("PLBKPL01XXX", "DEBKDE01XXX")
        self.assertEqual(route, ["PLBKPL01XXX", "DEBKDE01XXX"])

    def test_external_eu_bank_skips_local_account_directory(self):
        external_xml = SAMPLE_XML.replace("UKBKGB01XXX", "BANKDEXX").replace(
            "GB29NWBK60161331926819",
            "DE89370400440532013000",
        )
        with patch("app.services.inbox.add_incoming") as inbox_add:
            result, status = handle_swift_message(external_xml)

            self.assertEqual(status, 202)
            self.assertEqual(result["receiver_bank"], "Deutsche Bank")
            inbox_add.assert_called_once()


if __name__ == "__main__":
    unittest.main()