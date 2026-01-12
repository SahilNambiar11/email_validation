import os
import secrets
import sqlite3
from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from email_validator import validate_email, EmailNotValidError
from email.message import EmailMessage
import smtplib
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
SMTP_HOST = "smtp.sendgrid.net"
SMTP_PORT = 587
SMTP_USER = "apikey"
SMTP_PASS = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# --- Setup FastAPI ---
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- Simple SQLite DB to store tokens ---
conn = sqlite3.connect("tokens.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS verification_tokens (
    email TEXT PRIMARY KEY,
    token TEXT,
    verified INTEGER DEFAULT 0
)
""")
conn.commit()

# --- Email validation ---
def verify_email_address(email: str):
    try:
        valid = validate_email(email, check_deliverability=True)
        return valid.email, "Syntax + MX OK ✅"
    except EmailNotValidError as e:
        return email, f"Invalid ❌ ({e})"

# --- Send SMTP email securely ---
def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()        # Secure TLS
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# --- Create verification token ---
def create_verification_token(email: str):
    token = secrets.token_urlsafe(16)
    c.execute("INSERT OR REPLACE INTO verification_tokens (email, token, verified) VALUES (?, ?, 0)", (email, token))
    conn.commit()
    return token

# --- Verify token endpoint ---
@app.get("/verify")
def verify_token(token: str):
    c.execute("SELECT email FROM verification_tokens WHERE token=? AND verified=0", (token,))
    row = c.fetchone()
    if row:
        email = row[0]
        c.execute("UPDATE verification_tokens SET verified=1 WHERE email=?", (email,))
        conn.commit()
        return {"status": "success", "email": email, "message": "Email verified!"}
    return {"status": "error", "message": "Invalid or already verified token"}

# --- Home page ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": ""})

# --- Form submission ---
@app.post("/send", response_class=HTMLResponse)
async def send(request: Request, background_tasks: BackgroundTasks, email: str = Form(...)):
    email_clean, status = verify_email_address(email)
    if "Invalid" in status:
        result = f"{email_clean} → {status}"
    else:
        # Generate token and link
        token = create_verification_token(email_clean)
        verification_link = f"{BASE_URL}/verify?token={token}"
        body = f"Hello! Please confirm your email by clicking this link:\n\n{verification_link}"
        
        # Send email in background
        background_tasks.add_task(send_email, email_clean, "Verify your email", body)
        result = f"{email_clean} → {status} → Verification email sent ✅"

    return templates.TemplateResponse("index.html", {"request": request, "result": result})
