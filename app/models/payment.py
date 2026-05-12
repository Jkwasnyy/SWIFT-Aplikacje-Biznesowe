from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentMessage:
    message_id: str
    instruction_id: str
    creation_datetime: str

    end_to_end_id: str
    uetr: str

    charge_bearer: str
    settlement_method: str
    settlement_date: str

    sender_name: str
    sender_bic: str
    sender_account: str

    receiver_name: str
    receiver_bic: str
    receiver_account: str

    amount: str
    currency: str

    remittance_info: str = ""

    def to_bank_payload(self):
        return {
            "message_id": self.message_id,
            "instruction_id": self.instruction_id,
            "creation_datetime": self.creation_datetime,

            "end_to_end_id": self.end_to_end_id,
            "uetr": self.uetr,

            "charge_bearer": self.charge_bearer,
            "settlement_method": self.settlement_method,
            "settlement_date": self.settlement_date,

            "sender_name": self.sender_name,
            "sender_bic": self.sender_bic,
            "sender_account": self.sender_account,

            "receiver_name": self.receiver_name,
            "receiver_bic": self.receiver_bic,
            "receiver_account": self.receiver_account,

            "amount": self.amount,
            "currency": self.currency,

            "remittance_info": self.remittance_info,
        }