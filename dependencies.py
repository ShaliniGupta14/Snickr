from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature
from dotenv import load_dotenv
import os

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
signer = URLSafeTimedSerializer(SECRET_KEY)

def get_current_user(request: Request):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        user_id = signer.loads(token, max_age=86400)
        return int(user_id)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session")

def make_session_cookie(user_id: int) -> str:
    return signer.dumps(str(user_id))