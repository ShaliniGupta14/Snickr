from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_connection
from dependencies import make_session_cookie
import hashlib, os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    nickname: str = Form(""),
    password: str = Form(...),
):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO Users (email, username, nickname, password) "
            "VALUES (%s, %s, %s, %s)",
            (email.strip(), username.strip(), nickname.strip(), hashed),
        )
        conn.commit()
        return RedirectResponse("/login", status_code=303)
    except Exception:
        conn.rollback()
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email or username already taken."},
        )
    finally:
        cursor.close()
        conn.close()

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT user_id, password FROM Users WHERE email = %s",
            (email.strip(),),
        )
        user = cursor.fetchone()
        if not user or not verify_password(password, user["password"]):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid email or password."},
            )
        token = make_session_cookie(user["user_id"])
        resp = RedirectResponse("/dashboard", status_code=303)
        resp.set_cookie(
            key="session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400,
        )
        return resp
    finally:
        cursor.close()
        conn.close()

@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp