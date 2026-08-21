from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProviderErrorCode(str, Enum):
    INSTAGRAM_UNAVAILABLE = "instagram_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"


_ERROR_MESSAGES = {
    ProviderErrorCode.INSTAGRAM_UNAVAILABLE: "This Instagram Reel is unavailable.",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "The Instagram provider is unavailable.",
    ProviderErrorCode.PROVIDER_TIMEOUT: "The Instagram provider timed out.",
    ProviderErrorCode.PROVIDER_INVALID_RESPONSE: (
        "The Instagram provider returned an invalid response."
    ),
}


class ApifyProviderError(RuntimeError):
    def __init__(self, code: ProviderErrorCode):
        self.code = code
        super().__init__(_ERROR_MESSAGES[code])


class ApifyRunStatus(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMING_OUT = "TIMING-OUT"
    TIMED_OUT = "TIMED-OUT"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"


class ApifyRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: ApifyRunStatus
    default_dataset_id: Optional[str] = None


class InstagramReelMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    shortcode: str
    canonical_url: str
    caption: Optional[str]
    owner_username: str
    thumbnail_url: str


class InstagramProfileMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    username: str
    external_urls: tuple[str, ...]


class ApifyRunData(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, populate_by_name=True)

    run_id: str = Field(alias="id")
    status: str
    default_dataset_id: Optional[str] = Field(default=None, alias="defaultDatasetId")


class ApifyReelItem(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, populate_by_name=True)

    short_code: str = Field(alias="shortCode")
    url: str
    caption: Optional[str]
    display_url: str = Field(alias="displayUrl")
    owner_username: str = Field(alias="ownerUsername")
    input_url: Optional[str] = Field(default=None, alias="inputUrl")
    error: Any = None
    error_description: Any = Field(default=None, alias="errorDescription")


class ApifyExternalUrl(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    url: str


class ApifyProfileItem(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, populate_by_name=True)

    username: str
    url: Optional[str] = None
    external_url: Optional[str] = Field(default=None, alias="externalUrl")
    external_urls: list[ApifyExternalUrl] = Field(
        default_factory=list, alias="externalUrls"
    )
    private: bool
    error: Any = None
    error_description: Any = Field(default=None, alias="errorDescription")
