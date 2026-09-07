from typing import List, Optional, Union

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    to: Union[str, List[str]] = Field(..., description="Příjemce nebo seznam příjemců")
    subject: str
    body: str
    html: bool = False
    cc: Optional[Union[str, List[str]]] = None
    bcc: Optional[Union[str, List[str]]] = None
    # Nepovinná kalendářní událost (raw iCalendar text) jako příloha .ics
    ics: Optional[str] = None
    ics_name: str = "udalost.ics"
    ics_method: str = "PUBLISH"
