"""Shared enum types for all ORM models."""

import enum


class UploadStatus(enum.Enum):
    """Lifecycle status of an Upload record."""

    ACTIVE = "ACTIVE"
    SOFT_DELETED = "SOFT_DELETED"


class RawTransactionStatus(enum.Enum):
    """Processing status of a RawTransaction row."""

    ACTIVE = "ACTIVE"
    DUPLICATE = "DUPLICATE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    PARSE_ERROR = "PARSE_ERROR"


class TransactionStatus(enum.Enum):
    """Lifecycle status of a Transaction record."""

    ACTIVE = "ACTIVE"
    SOFT_DELETED = "SOFT_DELETED"


class TransactionCategory(enum.Enum):
    """Internal classification category for a Transaction."""

    OPTIONS_SELL_TO_OPEN = "OPTIONS_SELL_TO_OPEN"
    OPTIONS_BUY_TO_OPEN = "OPTIONS_BUY_TO_OPEN"
    OPTIONS_BUY_TO_CLOSE = "OPTIONS_BUY_TO_CLOSE"
    OPTIONS_SELL_TO_CLOSE = "OPTIONS_SELL_TO_CLOSE"
    OPTIONS_EXPIRED = "OPTIONS_EXPIRED"
    OPTIONS_ASSIGNED = "OPTIONS_ASSIGNED"
    OPTIONS_EXERCISED = "OPTIONS_EXERCISED"
    EQUITY_BUY = "EQUITY_BUY"
    EQUITY_SELL = "EQUITY_SELL"
    DIVIDEND = "DIVIDEND"
    TRANSFER = "TRANSFER"
    INTEREST = "INTEREST"
    FEE = "FEE"
    JOURNAL = "JOURNAL"
    OTHER = "OTHER"


class OptionType(enum.Enum):
    """Option contract type."""

    CALL = "CALL"
    PUT = "PUT"


class PositionDirection(enum.Enum):
    """Direction of an options position."""

    LONG = "LONG"
    SHORT = "SHORT"


class OptionsPositionStatus(enum.Enum):
    """Lifecycle status of an OptionsPosition."""

    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    ASSIGNED = "ASSIGNED"
    EXERCISED = "EXERCISED"


class LegRole(enum.Enum):
    """Role of a leg in an options position."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"


class EquityPositionSource(enum.Enum):
    """How an equity position was acquired."""

    PURCHASE = "PURCHASE"
    ASSIGNMENT = "ASSIGNMENT"
    EXERCISE = "EXERCISE"


class EquityPositionStatus(enum.Enum):
    """Lifecycle status of an EquityPosition."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
