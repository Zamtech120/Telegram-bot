from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

API_KEY = os.getenv("API_KEY") or "my_secure_api_key_123"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class EmailCheckRequest(BaseModel):
    emails: list[str]

# Simulated database or logic
SIMULATED_DATABASE = {
    "active@example.com": "yes",
    "flagged@example.com": "no",
    "blocked@example.com": "captcha",
    "error@example.com": "error"
}

@app.get("/status")
def status_check():
    return {"status": "ok"}

@app.post("/check_emails")
def check_emails(request: Request, payload: EmailCheckRequest):
    api_key = request.headers.get("x-api-key")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    results = {}
    for email in payload.emails:
        # Simulate some results based on the test dictionary
        results[email] = SIMULATED_DATABASE.get(email.lower(), "no")

    return results
