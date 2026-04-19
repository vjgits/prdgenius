"""
PRDGenius — AI-Powered PRD Generator
Production-ready: Security hardened, Stripe payments, Admin role
"""

import os, sqlite3, hashlib, secrets, json, io, re, time, hmac
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from functools import wraps
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, validator
import anthropic
from dotenv import load_dotenv
from prd_prompt import PRD_SYSTEM_PROMPT, build_prd_prompt

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "prd_genius.db")

# ─── Rate limiting store ──────────────────────────────────────────────────────
_rate_store: dict = {}

def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> bool:
    now = time.time()
    calls = _rate_store.get(key, [])
    calls = [t for t in calls if now - t < window_seconds]
    if len(calls) >= max_calls:
        return False
    calls.append(now)
    _rate_store[key] = calls
    return True

# ─── Security middleware ──────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

# ─── DB ──────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            plan TEXT DEFAULT 'free',
            role TEXT DEFAULT 'user',
            prds_used_this_month INTEGER DEFAULT 0,
            month_reset_date TEXT,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS prds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            feature_name TEXT NOT NULL,
            format_style TEXT NOT NULL,
            inputs TEXT NOT NULL,
            output TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
        CREATE INDEX IF NOT EXISTS idx_prds_user ON prds(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
    """)
    conn.commit()

    # Create admin user if not exists
    admin_email = "admin@prdgenius.ai"
    admin_pw = hash_password("Chocolate47##")
    existing = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (name, email, password_hash, plan, role) VALUES (?,?,?,?,?)",
            ("Admin", admin_email, admin_pw, "admin", "admin")
        )
        conn.commit()
    else:
        conn.execute("UPDATE users SET role='admin', plan='admin' WHERE email=?", (admin_email,))
        conn.commit()

    conn.close()

def hash_password(password: str) -> str:
    salt = os.getenv("PASSWORD_SALT", "prdgenius_salt_2025")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn = get_db()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires))
    conn.commit(); conn.close()
    return token

def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token or len(token) > 100: return None
    conn = get_db()
    row = conn.execute("""
        SELECT u.* FROM users u JOIN sessions s ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    """, (token, datetime.utcnow().isoformat())).fetchone()
    conn.close()
    return dict(row) if row else None

def require_user(request: Request):
    user = get_current_user(request)
    if not user: raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_admin(request: Request):
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

FREE_PLAN_LIMIT  = 1
PRO_PLAN_LIMIT   = 100
ADMIN_PLAN_LIMIT = 999999

def get_plan_limit(user: dict) -> int:
    if user.get("role") == "admin" or user.get("plan") == "admin": return ADMIN_PLAN_LIMIT
    if user.get("plan") == "pro": return PRO_PLAN_LIMIT
    return FREE_PLAN_LIMIT

def check_and_increment_usage(user_id: int):
    conn = get_db()
    user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    # Admin bypass
    if user.get("role") == "admin" or user.get("plan") == "admin":
        conn.close()
        return {"allowed": True}
    month_start = datetime.utcnow().replace(day=1).date().isoformat()
    if user["month_reset_date"] != month_start:
        conn.execute("UPDATE users SET prds_used_this_month = 0, month_reset_date = ? WHERE id = ?",
                     (month_start, user_id))
        conn.commit(); user["prds_used_this_month"] = 0
    limit = get_plan_limit(user)
    if user["prds_used_this_month"] >= limit:
        conn.close()
        plan_name = "Pro" if user["plan"] == "pro" else "free"
        return {"allowed": False, "message": f"Monthly limit reached on {plan_name} plan."}
    conn.execute("UPDATE users SET prds_used_this_month = prds_used_this_month + 1 WHERE id = ?", (user_id,))
    conn.commit(); conn.close()
    return {"allowed": True}

# ─── Word doc generation ──────────────────────────────────────────────────────
def _add_inline_formatting(paragraph, text: str):
    parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2]); run.bold = True
        elif part.startswith('`') and part.endswith('`'):
            from docx.shared import Pt, RGBColor
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Courier New'; run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0x6D, 0x28, 0xD9)
        elif part:
            paragraph.add_run(part)

def markdown_to_docx(markdown_text: str, feature_name: str) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.5); section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3); section.right_margin = Cm(2.5)
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(11)
    INDIGO = RGBColor(0x43, 0x38, 0xCA); BLUE = RGBColor(0x1D, 0x4E, 0xD8); SLATE = RGBColor(0x1E, 0x29, 0x3B)
    lines = markdown_text.split('\n'); i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip()
        if re.match(r'^# [^#]', s):
            h = doc.add_heading(s[2:].strip(), level=1)
            for r in h.runs: r.font.color.rgb = INDIGO; r.font.size = Pt(22)
        elif re.match(r'^## [^#]', s):
            h = doc.add_heading(s[3:].strip(), level=2)
            for r in h.runs: r.font.color.rgb = BLUE; r.font.size = Pt(15)
        elif re.match(r'^### ', s):
            h = doc.add_heading(s[4:].strip(), level=3)
            for r in h.runs: r.font.color.rgb = SLATE; r.font.size = Pt(12)
        elif s == '---':
            doc.add_paragraph()
        elif s.startswith('|') and i+1 < len(lines) and re.match(r'^\|[-| :]+\|', lines[i+1].strip()):
            headers = [h.strip() for h in s.split('|') if h.strip()]
            ncols = len(headers)
            if ncols == 0: i += 1; continue
            table = doc.add_table(rows=1, cols=ncols); table.style = 'Table Grid'
            hrow = table.rows[0]
            for j, h in enumerate(headers):
                cell = hrow.cells[j]; cell.text = h; p = cell.paragraphs[0]
                p.runs[0].bold = True; p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                tc = cell._tc; tcPr = tc.get_or_add_tcPr()
                shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), '4338CA'); tcPr.append(shd)
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].split('|') if c != '']
                cells = [c for c in cells if c.strip() not in ('', ' ')]
                row = table.add_row()
                for j in range(min(len(cells), ncols)): row.cells[j].text = cells[j]
                i += 1
            doc.add_paragraph(); continue
        elif re.match(r'^- \[.?\] ', s):
            checked = bool(re.match(r'^- \[[xX]\]', s))
            text = re.sub(r'^- \[.?\] ?', '', s)
            p = doc.add_paragraph(); p.add_run('☑ ' if checked else '☐ ')
            _add_inline_formatting(p, text)
        elif re.match(r'^[-*] ', s):
            p = doc.add_paragraph(style='List Bullet'); _add_inline_formatting(p, s[2:].strip())
        elif re.match(r'^\d+\. ', s):
            p = doc.add_paragraph(style='List Number'); _add_inline_formatting(p, re.sub(r'^\d+\. ', '', s))
        elif s.startswith('>'):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.4)
            run = p.add_run(s[1:].strip()); run.italic = True; run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
        elif s == '':
            pass
        else:
            p = doc.add_paragraph(); _add_inline_formatting(p, s)
        i += 1
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf.getvalue()

# ─── App ─────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="PRDGenius", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

# ─── Pages ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user = get_current_user(request)
    if user: return RedirectResponse("/app")
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request): return RedirectResponse("/app")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if get_current_user(request): return RedirectResponse("/app")
    return templates.TemplateResponse("signup.html", {"request": request})

@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    conn = get_db()
    prds = [dict(p) for p in conn.execute(
        "SELECT * FROM prds WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user["id"],)).fetchall()]
    conn.close()
    last_prd = prds[0] if prds else None
    limit = get_plan_limit(user)
    at_limit = (user["plan"] not in ("pro", "admin") and
                user.get("role") != "admin" and
                user["prds_used_this_month"] >= FREE_PLAN_LIMIT)
   