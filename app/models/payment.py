from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentMessage:
    message_id: str
    instruction_id: str
    creation_datetime: str
    charge_bearer: str
    sender_name: str
    sender_bic: str
    receiver_name: str
    receiver_bic: str
    amount: str
    currency: str
    remittance_info: str = ""

    def to_bank_payload(self):
        return {
            "message_id": self.message_id,
            "instruction_id": self.instruction_id,
            "creation_datetime": self.creation_datetime,
            "charge_bearer": self.charge_bearer,
            "sender_name": self.sender_name,
            "sender_bic": self.sender_bic,
            "receiver_name": self.receiver_name,
            "receiver_bic": self.receiver_bic,
            "amount": self.amount,
            "currency": self.currency,
            "remittance_info": self.remittance_info,
        }