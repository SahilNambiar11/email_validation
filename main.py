import os
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from email_validator import validate_email, EmailNotValidError
from email.message import EmailMessage
import aiosmtplib
from dotenv import load_dotenv
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


# Load .env variables
load_dotenv()
SMTP_HOST = "smtp.sendgrid.net"
SMTP_PORT = 587
SMTP_USER = "apikey"  # Always "apikey" for SendGrid
SMTP_PASS = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

app = FastAPI()
templates = Jinja2Templates(directory="templates")  # Make a folder called templates

# --- Email validation ---
def verify_email_address(email: str):
    try:
        valid = validate_email(email, check_deliverability=True)
        return valid.email, "Syntax + MX OK ✅"
    except EmailNotValidError as e:
        return email, f"Invalid ❌ ({e})"

# --- Send email function ---
async def send_email(to_email: str):
    try:
        msg = EmailMessage()
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = "Email Verification Test"
        msg.set_content("Hello! This is a test verification email from FastAPI + SendGrid.")

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASS,
            tls_context=ssl_context
        )
        return "Email sent successfully ✅"
    except Exception as e:
        return f"Failed to send email ❌ ({e})"

# --- Home page ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "result": ""})

# --- Form submission ---
@app.post("/send", response_class=HTMLResponse)
async def send(request: Request, email: str = Form(...)):
    try:
        email_clean, status = verify_email_address(email)
        if "Invalid" in status:
            result = f"{email_clean} → {status}"
        else:
            send_status = await send_email(email_clean)
            result = f"{email_clean} → {status} → {send_status}"
    except Exception as e:
        result = f"Internal server error ❌ ({e})"
    return templates.TemplateResponse("index.html", {"request": request, "result": result})
