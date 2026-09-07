from typing import List, Optional, Union

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    to: Union[str, List[str]] = Field(..., description="Příjemce nebo seznam příjemců")
    subject: str
    body: str
    html: bool = False
    cc: Optional[Union[str, List[str]]] = None
    bcc: Optional[Union[str, List[str]]] = None
