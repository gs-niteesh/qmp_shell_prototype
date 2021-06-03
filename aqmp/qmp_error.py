from error import AQMPError
from message import Message
from models import ErrorInfo


class ExecuteError(AQMPError):
    """Execution statement returned failure."""
    def __init__(self,
                 sent: Message,
                 received: Message,
                 error: ErrorInfo):
        super().__init__()
        self.sent = sent
        self.received = received
        self.error = error

    def __str__(self) -> str:
        return self.error.desc
