from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def normalize_email(value: str) -> str:
    value = value.strip().casefold()
    if len(value) > 254 or value.count("@") != 1 or any(c.isspace() for c in value):
        raise ValueError("Enter a valid email address.")
    local, domain = value.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address.")
    return value


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value)


class UserOutput(BaseModel):
    id: str
    email: str


class AuthOutput(BaseModel):
    user: UserOutput
    csrf_token: str
