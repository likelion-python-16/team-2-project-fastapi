from pydantic import BaseModel, EmailStr

class SignUpIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    name: str | None = None

class LoginIn(BaseModel):
    login: str        # username 또는 email
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
