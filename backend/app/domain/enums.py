from enum import Enum


class Direction(str, Enum):
    IN = "in"
    OUT = "out"


class CashEventStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"


class InvoiceStatus(str, Enum):
    PAID = "paid"
    DUE = "due"
    OVERDUE = "overdue"


class Decision(str, Enum):
    ACT = "act"
    ESCALATE = "escalate"


class Tone(str, Enum):
    GENTLE = "gentle"
    FIRM = "firm"
