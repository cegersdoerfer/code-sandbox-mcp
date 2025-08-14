from pydantic import BaseModel
from enum import Enum


class Language(Enum):
    PYTHON = "python"
    BASH = "bash"

class KernelOutput(BaseModel):
    mime_type: str
    content: str
    is_error: bool
