import json

class Ticket:
    def __init__(self) -> None:
        self.sender = "Backtester"
        self.receiver = None
        self.type = None
        self.data = None

    def from_object(self, newTicket):
        self.receiver = newTicket.get('receiver', self.receiver)
        self.type = newTicket.get('type', self.type)
        self.data = newTicket.get('data', self.data)

        return json.dumps({
            'sender': self.sender,
            'receiver': self.receiver,
            'type': self.type,
            'data': self.data
        }, allow_nan=True)
