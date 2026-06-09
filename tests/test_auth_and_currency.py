import unittest

from app.core.auth import issue_token
from app.core.config import get_currency_for_bic, build_bank_claim
from app.services.parser import parse_xml


SAMPLE_XML_US = """<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr><MsgId>MSG-US</MsgId><CreDtTm>2026-05-12T09:30:00Z</CreDtTm></GrpHdr>
    <CdtTrfTxInf>
      <PmtId><InstrId>INST-US</InstrId><UETR>aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee</UETR></PmtId>
      <ChrgBr>SHAR</ChrgBr>
      <Dbtr><Nm>Sender</Nm></Dbtr>
      <DbtrAcct><Id><IBAN>PL61109010140000071219812874</IBAN></Id></DbtrAcct>
      <DbtrAgt><FinInstnId><BICFI>PLBKPL01XXX</BICFI></FinInstnId></DbtrAgt>
      <Cdtr><Nm>Receiver</Nm></Cdtr>
      <CdtrAgt><FinInstnId><BICFI>USBKUS01XXX</BICFI></FinInstnId></CdtrAgt>
      <CdtrAcct><Id><Othr><Id>US123456789012345678901234</Id></Othr></Id></CdtrAcct>
      <IntrBkSttlmAmt Ccy="PLN">50.00</IntrBkSttlmAmt>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""


class AuthAndCurrencyTestCase(unittest.TestCase):
    def test_currency_from_receiver_bank(self):
        self.assertEqual(get_currency_for_bic("USBKUS01XXX"), "USD")
        self.assertEqual(get_currency_for_bic("UKBKGB01XXX"), "GBP")
        self.assertEqual(get_currency_for_bic("DEBKDE01XXX"), "EUR")
        self.assertEqual(get_currency_for_bic("PLBKPL01XXX"), "PLN")

    def test_parser_overrides_xml_currency_with_destination_bank(self):
        message = parse_xml(SAMPLE_XML_US)
        self.assertEqual(message.receiver_bic, "USBKUS01XXX")
        self.assertEqual(message.currency, "USD")

    def test_token_contains_single_bank_data(self):
        token = issue_token("test-client", "test-secret", bank_bic="PLBKPL01XXX")
        self.assertIsNotNone(token)
        self.assertIn("bank", token)
        self.assertEqual(token["bank"]["bic"], "PLBKPL01XXX")
        self.assertEqual(token["bank"]["name"], "Bank Polska 1")
        self.assertEqual(token["bank"]["country"], "PL")
        self.assertEqual(token["bank"]["currency"], "PLN")
        self.assertEqual(token["banks"], ["PLBKPL01XXX"])

    def test_build_bank_claim_shape(self):
        claim = build_bank_claim("USBKUS01XXX")
        self.assertEqual(
            claim,
            {
                "bic": "USBKUS01XXX",
                "name": "Bank USA 1",
                "country": "US",
                "currency": "USD",
            },
        )


if __name__ == "__main__":
    unittest.main()
