"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""
import builtins
import google.protobuf.descriptor
import google.protobuf.message
import sys

if sys.version_info >= (3, 8):
    import typing as typing_extensions
else:
    import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing_extensions.final
class FieldElement(google.protobuf.message.Message):
    """StarkNet field element.

    Encoded as 4 packed uint64
    """

    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    LO_LO_FIELD_NUMBER: builtins.int
    LO_HI_FIELD_NUMBER: builtins.int
    HI_LO_FIELD_NUMBER: builtins.int
    HI_HI_FIELD_NUMBER: builtins.int
    lo_lo: builtins.int
    lo_hi: builtins.int
    hi_lo: builtins.int
    hi_hi: builtins.int
    def __init__(
        self,
        *,
        lo_lo: builtins.int = ...,
        lo_hi: builtins.int = ...,
        hi_lo: builtins.int = ...,
        hi_hi: builtins.int = ...,
    ) -> None: ...
    def ClearField(
        self,
        field_name: typing_extensions.Literal[
            "hi_hi", b"hi_hi", "hi_lo", b"hi_lo", "lo_hi", b"lo_hi", "lo_lo", b"lo_lo"
        ],
    ) -> None: ...

global___FieldElement = FieldElement