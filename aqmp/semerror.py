"""
This module provides QAPI-schema-aware semantic errors.

Ideally, something like this would be generated and used by an SDK layer
as part of the QEMU build (or another tool) and handled at that
level. This is just a prototype toy that explores a possible technique
for providing semantic QMP exception classes.
"""

from enum import Enum

from qmp_error import ExecuteError


class ErrorClass(Enum):
    """Based on qapi/error.json's QapiErrorClass."""
    # pylint: disable=invalid-name
    generic_error = "GenericError"
    command_not_found = "CommandNotFound"
    device_not_active = "DeviceNotActive"
    device_not_found = "DeviceNotFound"
    kvm_missing_cap = "KVMMissingCap"


class GenericError(ExecuteError):
    """
    this is used for errors that don't require a specific error
    class. This should be the default case for most errors
    """


class CommandNotFound(ExecuteError):
    """the requested command has not been found"""


class DeviceNotActive(ExecuteError):
    """a device has failed to be become active"""


class DeviceNotFound(ExecuteError):
    """the requested device has not been found"""


class KVMMissingCap(ExecuteError):
    """
    the requested operation can't be fulfilled because a
    required KVM capability is missing
    """


_MAP = {
    ErrorClass.generic_error: GenericError,
    ErrorClass.command_not_found: CommandNotFound,
    ErrorClass.device_not_active: DeviceNotActive,
    ErrorClass.device_not_found: DeviceNotFound,
    ErrorClass.kvm_missing_cap: KVMMissingCap,
}


def upgrade_exception_class(err: ExecuteError) -> ExecuteError:
    try:
        enum_val = ErrorClass(err.error.class_)
    except ValueError:
        # Unrecognized error class, upgrade not possible.
        return err

    cls = _MAP[enum_val]
    exc = cls(err.sent, err.received, err.error)
    exc.__cause__ = err.__cause__
    exc.__context__ = err.__context__
    exc.__traceback__ = err.__traceback__
    return exc
