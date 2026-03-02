from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN_NETWORK_REFERENCE = "UNKNOWN_NETWORK_REFERENCE"
    INVALID_CIDR = "INVALID_CIDR"
    DUPLICATE_NETWORK_NAME = "DUPLICATE_NETWORK_NAME"
    DUPLICATE_NODE_NAME = "DUPLICATE_NODE_NAME"
    NODE_WITHOUT_NETWORK = "NODE_WITHOUT_NETWORK"
    DUPLICATE_NODE_NETWORK = "DUPLICATE_NODE_NETWORK"
    UNSUPPORTED_BLUEPRINT_SCHEMA = "UNSUPPORTED_BLUEPRINT_SCHEMA"


class ErrorDetail(dict):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(code=code.value, message=message)


def http_error(status_code: int, code: ErrorCode, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=ErrorDetail(code=code, message=message))
