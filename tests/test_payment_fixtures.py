from pathlib import Path
import unittest

from app.services.swift_service import handle_swift_message


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "mocks" / "test_payments"


class PaymentFixtureTestCase(unittest.TestCase):
    def _load(self, name: str) -> str:
        return (FIXTURE_DIR / name).read_text(encoding="utf-8")

    def test_payment1_happy_path(self):
        result, status = handle_swift_message(self._load("PLBKPL01_do_UKBKGB01.xml"))

        self.assertEqual(status, 202)
        self.assertEqual(result["receiver_bank"], "Bank UK 1")
        self.assertEqual(result["route"], ["PLBKPL01XXX", "UKBKGB01XXX"])

    def test_payment2_multihop_route(self):
        result, status = handle_swift_message(self._load("PLBKPL01_do_USBKUS01.xml"))

        self.assertEqual(status, 202)
        self.assertEqual(result["receiver_bank"], "Bank USA 1")
        self.assertGreaterEqual(len(result["route"]), 3)

    def test_payment3_closed_account(self):
        result, status = handle_swift_message(self._load("PLBKPL01_do_UKBKGB01_konto_zamkniete.xml"))

        self.assertEqual(status, 422)
        self.assertEqual(result["error"], "Receiver account closed")

    def test_payment4_missing_account(self):
        result, status = handle_swift_message(self._load("PLBKPL01_do_UKBKGB02_konto_nieistnieje.xml"))

        self.assertEqual(status, 404)
        self.assertEqual(result["error"], "Receiver account not found")


if __name__ == "__main__":
    unittest.main()