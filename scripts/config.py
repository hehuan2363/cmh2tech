"""Campaign configuration. Edit this file for new campaigns."""
import os

# --- API Keys (set via environment variables) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MV_API_KEY = os.environ.get("MV_API_KEY", "")

# --- Gemini ---
GEMINI_MODEL = "gemini-3-flash-preview"

# --- SMTP Verification ---
SMTP_TIMEOUT = 10
EHLO_DOMAIN = "cmh2.tech"
SENDER_EMAIL = "verify@cmh2.tech"

# --- Processing ---
SAVE_EVERY = 50
DELAY_BETWEEN = 0.3
DELAY_BETWEEN_DOMAINS = 1.0

# --- Paths ---
LEADS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "coldemails", "Leads")
