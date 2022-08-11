from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Union

from pydantic import AnyHttpUrl, BaseModel, Extra, validator

from . import ids


class InitialCreationType(Enum):
    ocr = "ocr"
    ebook = "ebook"
    input = "input"


class CopyrightStatus(Enum):
    UNKNOWN = "Unknown"
    COPYRIGHTED = "Copyrighted"
    PUBLIC_DOMAIN = "Public Domain"


class Copyright(BaseModel):
    status: CopyrightStatus = CopyrightStatus.UNKNOWN
    notice: Optional[str] = ""
    info_url: Optional[AnyHttpUrl] = None

    class Config:
        extra = Extra.forbid


class LicenseType(Enum):
    # based on https://creativecommons.org/licenses/

    CC0 = "CC0"
    PUBLIC_DOMAIN_MARK = "Public Domain Mark"
    CC_BY = "CC BY"
    CC_BY_SA = "CC BY-SA"
    CC_BY_ND = "CC BY-ND"
    CC_BY_NC = "CC BY-NC"
    CC_BY_NC_SA = "CC BY-NC-SA"
    CC_BY_NC_ND = "CC BY-NC-ND"


class PechaMetadata(BaseModel):
    id: str = None
    legacy_id: Optional[str] = None
    ocr_import_info: Optional[Dict] = {}
    default_language: str = None
    source: str = None
    ocr_info: Optional[Dict] = None
    source_file: str = None
    initial_creation_type: InitialCreationType
    imported: datetime = None
    last_modified: datetime = None
    parser: AnyHttpUrl = None
    source_metadata: Optional[Dict] = None  # place to dump any metadata from the source
    statistics: Optional[Dict] = None
    quality: Optional[Dict] = None
    bases: Optional[Dict[str, Dict]] = {}
    copyright: Copyright = None
    license: LicenseType = None

    @validator("imported", pre=True, always=True)
    def set_imported_date(cls, v):
        return v or datetime.now()

    @validator("last_modified", pre=True, always=True)
    def set_last_modified_date(cls, v):
        return v or datetime.now()

    @validator("copyright", pre=True, always=True)
    def set_copyright_info(cls, v):
        return v or Copyright()

    def update_last_modified_date(self):
        self.last_modified = datetime.now()

    # class Config:
    #     extra = Extra.forbid


class InitialPechaMetadata(PechaMetadata):
    ocr_word_median_confidence_index: float = None
    ocr_word_mean_confidence_index: float = None
    bases: Dict = {}

    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_initial_pecha_id()


class OpenPechaMetadata(PechaMetadata):
    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_open_pecha_id()


class DiplomaticPechaMetadata(PechaMetadata):
    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or ids.get_diplomatic_id()
