from typing import ClassVar as _ClassVar
from typing import Optional as _Optional

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message

DESCRIPTOR: _descriptor.FileDescriptor

class FieldElement(_message.Message):
    __slots__ = ["lo_lo", "lo_hi", "hi_lo", "hi_hi"]
    LO_LO_FIELD_NUMBER: _ClassVar[int]
    LO_HI_FIELD_NUMBER: _ClassVar[int]
    HI_LO_FIELD_NUMBER: _ClassVar[int]
    HI_HI_FIELD_NUMBER: _ClassVar[int]
    lo_lo: int
    lo_hi: int
    hi_lo: int
    hi_hi: int
    def __init__(
        self,
        lo_lo: _Optional[int] = ...,
        lo_hi: _Optional[int] = ...,
        hi_lo: _Optional[int] = ...,
        hi_hi: _Optional[int] = ...,
    ) -> None: ...
