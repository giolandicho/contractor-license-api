from enum import Enum
from typing import Optional
from pydantic import BaseModel, field_validator


class StateCode(str, Enum):
    CA = "CA"
    TX = "TX"
    FL = "FL"
    NY = "NY"


class VerifyParams(BaseModel):
    license_number: str
    state: StateCode

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("license_number cannot be empty")
        return v


class SearchParams(BaseModel):
    name: str
    state: StateCode
    limit: int = 10

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v: int) -> int:
        if v < 1:
            return 1
        if v > 50:
            return 50
        return v
