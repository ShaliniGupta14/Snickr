from pydantic import BaseModel
from typing import Optional

class RegisterForm(BaseModel):
    email: str
    username: str
    nickname: Optional[str] = None
    password: str

class LoginForm(BaseModel):
    email: str
    password: str

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class InviteToWorkspace(BaseModel):
    email: str

class ChannelCreate(BaseModel):
    name: str
    type: str

class InviteToChannel(BaseModel):
    username: str

class MessageCreate(BaseModel):
    body: str

class DirectChannelCreate(BaseModel):
    target_username: str