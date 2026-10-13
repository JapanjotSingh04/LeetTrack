"""Validated API request models."""
import re
from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Username may contain letters, numbers, dots, underscores, and hyphens.")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower()


class QuestionCompleteRequest(BaseModel):
    question_id: int = Field(gt=0)
    platform: str = Field(min_length=1, max_length=50)
    difficulty: str = Field(pattern="^(Easy|Medium|Hard)$")


class RevisionCompleteRequest(BaseModel):
    question_id: int = Field(gt=0)
    platform: str = Field(min_length=1, max_length=50)
    difficulty: str = Field(pattern="^(Easy|Medium|Hard)$")
    revision_counter: int = Field(ge=0)


class ErrorResponse(BaseModel):
    detail: str
