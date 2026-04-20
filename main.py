"""
PRDGenius – production FastAPI back-end
"""
import io, os, re, uuid, json, hashlib, sqlite3, logging, asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import anthropic
import stripe
from docx import Document
from docx.shared import Inches, Pt

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Rate limiting store ──────────────────────────────────────────────────────
_rate_store: dict = {}

def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> bool:
    now = datetime.utcnow().timestamp()
    calls = _rate_store.get(key, [])
    calls = [t for t in calls if now - t < window_seconds]
    if len(calls) >= max_calls:
        return False
    calls.append(now)
    _rate_store[key] = calls
    return True

# ─── Allowed email domains (blocks throwaway email abuse) ─────────────────────
ALLOWED_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "icloud.com", "protonmail.com", "me.com", "mac.com",
    "live.com", "msn.com", "ymail.com", "googlemail.com",
    "aol.com", "proton.me", "fastmail.com", "hey.com",
    "zoho.com", "mail.com", "pm.me", "tutanota.com",
    "prdgenius.ai"
}

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH                = os.getenv("DB_PATH", "/data/prd_genius.db")
PASSWORD_SALT          = os.getenv("PASSWORD_SALT", "prdgenius_s3cur3_s4lt_2024")
PRODUCTION             = os.getenv("PRODUCTION", "false").lower() == "true"
FREE_PLAN_LIMIT        = 1
stripe.api_key         = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID        = os.getenv("STRIPE_PRICE_ID", "")
STRIPE_YEARLY_PRICE_ID = os.getenv("STRIPE_YEARLY_PRICE_ID", "")
BASE_URL               = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                     TEXT PRIMARY KEY,
            name                   TEXT NOT NULL,
            email                  TEXT UNIQUE NOT NULL,
            password_hash          TEXT NOT NULL,
            plan                   TEXT NOT NULL DEFAULT 'free',
            role                   TEXT NOT NULL DEFAULT 'user',
            stripe_customer_id     TEXT,
            stripe_subscription_id TEXT,
            prds_used_this_month   INTEGER NOT NULL DEFAULT 0,
            created_at             TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS prds (
            id           TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            title        TEXT NOT NULL,
            content      TEXT NOT NULL,
            format_style TEXT NOT NULL,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token      TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    existing = [r[1] for r in conn.execute("PRAGMA table_info(prds)").fetchall()]
    for col in ["target_users","key_features","success_metrics","company_stage","additional_context"]:
        if col not in existing:
            conn.execute(f"ALTER TABLE prds ADD COLUMN {col} TEXT DEFAULT ''")
    conn.commit()
    admin_email = "admin@prdgenius.ai"
    admin_pw    = hash_password("Chocolate47##")
    existing    = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash, plan, role) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), "Admin", admin_email, admin_pw, "admin", "admin")
        )
    else:
        conn.execute("UPDATE users SET role='admin', plan='admin' WHERE email=?", (admin_email,))
    conn.commit()
    conn.close()

# ─── Auth helpers ─────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(f"{PASSWORD_SALT}{password}".encode()).hexdigest()

def create_session(user_id: str) -> str:
    token   = str(uuid.uuid4())
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn    = get_db()
    conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                 (token, user_id, expires))
    conn.commit(); conn.close()
    return token

def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("session")
    if not token: return None
    conn = get_db()
    row  = conn.execute(
        "SELECT s.user_id, s.expires_at FROM sessions s WHERE s.token=?", (token,)
    ).fetchone()
    if not row: conn.close(); return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit(); conn.close(); return None
    user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
    conn.close()
    return dict(user) if user else None

# ─── Plan helpers ─────────────────────────────────────────────────────────────
def get_plan_limit(user: dict) -> int:
    if user.get("role") == "admin" or user.get("plan") in ("pro", "admin", "yearly"):
        return 999999
    return FREE_PLAN_LIMIT

# ─── Security Middleware ──────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"]  = "nosniff"
        response.headers["X-Frame-Options"]          = "DENY"
        response.headers["X-XSS-Protection"]         = "1; mode=block"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        return response

# ─── DOCX helpers ─────────────────────────────────────────────────────────────
def _add_inline_formatting(paragraph, text: str):
    for part in re.split(r'(\*\*.*?\*\*|`.*?`)', text):
        if part.startswith('**') and part.endswith('**'):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith('`') and part.endswith('`'):
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Courier New'; run.font.size = Pt(9)
        else:
            paragraph.add_run(part)

def markdown_to_docx(md: str) -> bytes:
    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(11)
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Inches(1)
        section.left_margin = section.right_margin = Inches(1.2)
    for s in md.split('\n'):
        if   s.startswith('# '):   doc.add_heading(s[2:],  level=1)
        elif s.startswith('## '):  doc.add_heading(s[3:],  level=2)
        elif s.startswith('### '): doc.add_heading(s[4:],  level=3)
        elif s.startswith(('- ','* ')):
            _add_inline_formatting(doc.add_paragraph(style='List Bullet'), s[2:].strip())
        elif re.match(r'^\d+\. ', s):
            _add_inline_formatting(doc.add_paragraph(style='List Number'), re.sub(r'^\d+\. ','',s))
        elif s.startswith('> '):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Inches(0.4)
            doc.add_paragraph().add_run(s[2:]).italic = True
        elif s.strip() == '': doc.add_paragraph()
        else: _add_inline_formatting(doc.add_paragraph(), s)
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
                   allow_methods=["GET","POST","DELETE"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

# ─── Pages ────────────────────────────────────────────────────────────────────
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
        "SELECT * FROM prds WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user["id"],)
    ).fetchall()]
    conn.close()
    at_limit = (user["plan"] not in ("pro","admin") and
                user.get("role") != "admin" and
                user["prds_used_this_month"] >= FREE_PLAN_LIMIT)
    return templates.TemplateResponse("app.html", {
        "request": request, "user": user, "prds": prds,
        "last_prd": prds[0] if prds else None,
        "at_limit": at_limit, "limit": get_plan_limit(user),
        "stripe_pub_key": STRIPE_PUBLISHABLE_KEY, "free_limit": FREE_PLAN_LIMIT, "pro_limit": 100
    })

@app.get("/upgrade", response_class=HTMLResponse)
async def upgrade_page(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    return templates.TemplateResponse("upgrade.html", {
        "request": request, "user": user, "stripe_pub_key": STRIPE_PUBLISHABLE_KEY, "free_limit": FREE_PLAN_LIMIT, "pro_limit": 100
    })

@app.get("/upgrade/success", response_class=HTMLResponse)
async def upgrade_success(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    return templates.TemplateResponse("upgrade_success.html", {"request": request, "user": user})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

# ─── Auth API ─────────────────────────────────────────────────────────────────
@app.post("/api/signup")
async def api_signup(
    request:  Request,
    name:     str = Form(...),
    email:    str = Form(...),
    password: str = Form(...)
):
    client_ip = request.client.host
    if not check_rate_limit(f"signup:{client_ip}", max_calls=3, window_seconds=600):
        return JSONResponse(
            {"error": "Too many signup attempts from your location. Please try again later."},
            status_code=429
        )
    email  = email.strip().lower()
    domain = email.split("@")[-1] if "@" in email else ""
    if domain not in ALLOWED_EMAIL_DOMAINS:
        return JSONResponse(
            {"error": f"Signups require a major email provider (Gmail, Yahoo, Outlook, iCloud, etc.). '{domain}' is not supported."},
            status_code=400
        )
    if len(password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters."}, status_code=400)
    conn     = get_db()
    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        conn.close()
        return JSONResponse({"error": "Email already registered."}, status_code=409)
    user_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, name, email, password_hash, plan, role) VALUES (?,?,?,?,?,?)",
        (user_id, name.strip(), email, hash_password(password), "free", "user")
    )
    conn.commit(); conn.close()
    token    = create_session(user_id)
    response = JSONResponse({"success": True, "redirect": "/app"})
    response.set_cookie("session", token, httponly=True, secure=PRODUCTION,
                        max_age=60*60*24*30, samesite="lax")
    return response

@app.post("/api/login")
async def api_login(
    request:  Request,
    email:    str = Form(...),
    password: str = Form(...)
):
    client_ip = request.client.host
    if not check_rate_limit(f"login:{client_ip}", max_calls=10, window_seconds=300):
        return JSONResponse(
            {"error": "Too many login attempts. Please try again in 5 minutes."},
            status_code=429
        )
    email = email.strip().lower()
    conn  = get_db()
    user  = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not user or user["password_hash"] != hash_password(password):
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)
    token    = create_session(user["id"])
    response = JSONResponse({"success": True, "redirect": "/app"})
    response.set_cookie("session", token, httponly=True, secure=PRODUCTION,
                        max_age=60*60*24*30, samesite="lax")
    return response

@app.post("/api/logout")
async def api_logout(request: Request):
    token = request.cookies.get("session")
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit(); conn.close()
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session")
    return response

# ─── PRD API ──────────────────────────────────────────────────────────────────
@app.post("/api/check-limit")
async def check_limit(request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    limit   = get_plan_limit(user)
    used    = user["prds_used_this_month"]
    allowed = used < limit
    plan    = user.get("plan", "free")
    name    = "Pro" if plan == "pro" else ("Admin" if plan == "admin" else "Free")
    return JSONResponse({
        "allowed": allowed, "used": used, "limit": limit, "plan": plan,
        "plan_name": name,
        "message": f"Monthly limit reached on {name} plan." if not allowed else ""
    })

@app.post("/api/generate")
async def generate_prd(request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    if not check_rate_limit(f"gen:{user['id']}", max_calls=5, window_seconds=60):
        return JSONResponse({"error": "Too many requests. Please wait a moment."}, status_code=429)
    limit = get_plan_limit(user)
    if user["prds_used_this_month"] >= limit:
        plan_name = "Pro" if user["plan"] == "pro" else "Free"
        return JSONResponse(
            {"error": f"Monthly limit reached on {plan_name} plan.", "upgrade": True},
            status_code=403
        )
    data            = await request.json()
    product_name    = data.get("product_name",    "").strip()
    problem         = data.get("problem",          "").strip()
    target_users    = data.get("target_users",     "").strip()
    key_features    = data.get("key_features",     "").strip()
    success_metrics = data.get("success_metrics",  "").strip()
    format_style       = data.get("format_style",      "standard").strip()
    company_stage      = data.get("company_stage",     "").strip()
    additional_context = data.get("additional_context", data.get("context", "")).strip()
    if not product_name or not problem:
        return JSONResponse({"error": "Product name and problem statement are required."}, status_code=400)
    format_instructions = {
        "standard":  "Write a comprehensive, well-structured PRD with clear sections.",
        "lean":      "Write a concise lean PRD focusing on essentials only. Keep it brief.",
        "agile":     "Write an agile-style PRD with user stories and acceptance criteria.",
        "technical": "Write a technical PRD with system requirements and engineering details.",
    }.get(format_style, "Write a comprehensive PRD.")

    prd_size = data.get("prd_size", "ai_choice").strip()
    size_config = {
        "brief":     (2000, "BRIEF: Cover only Executive Summary, Problem Statement, top 3 Features, Success Metrics, and Risks. Be concise. You MUST complete all 5 sections within your token limit."),
        "medium":    (4000, "MEDIUM: Cover all 10 standard PRD sections with clear, actionable detail. You MUST complete all 10 sections within your token limit."),
        "extensive": (6000, "EXTENSIVE: Cover all 10 sections with rich depth — detailed user stories, edge cases, technical specs, and comprehensive risk analysis. You MUST complete all 10 sections within your token limit."),
    }
    max_tok, size_instruction = size_config.get(prd_size, size_config["medium"])
    prompt = f"""You are an expert product manager. Create a professional Product Requirements Document (PRD).

{format_instructions}

SIZE REQUIREMENT: {size_instruction}

CRITICAL: You must complete ALL sections within a single response. Do not truncate. Every section must have a proper ending. Write efficiently to fit everything in.

Product Details:
- Product Name: {product_name}
- Problem Statement: {problem}
- Target Users: {target_users or 'Not specified'}
- Key Features: {key_features or 'Not specified'}
- Success Metrics: {success_metrics or 'Not specified'}

Generate a complete PRD in Markdown format with all of these sections:
1. Executive Summary
2. Problem Statement & Background
3. Goals & Success Metrics
4. User Personas & Target Audience
5. Feature Requirements (P0/P1/P2 priority)
6. User Stories
7. Technical Considerations
8. Timeline & Milestones
9. Risks & Mitigations
10. Open Questions

Make it detailed, actionable, and ready for engineering teams."""
    try:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        _r = await _client.messages.create(
            model="claude-sonnet-4-6", max_tokens=max_tok,
            messages=[{"role": "user", "content": prompt}]
        )
        content = _r.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return JSONResponse({"error": "AI generation failed. Please try again."}, status_code=500)
    prd_id = str(uuid.uuid4())
    conn   = get_db()
    conn.execute(
        "INSERT INTO prds (id, user_id, title, content, format_style, target_users, key_features, success_metrics, company_stage, additional_context) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (prd_id, user["id"], product_name, content, format_style, target_users, key_features, success_metrics, company_stage, additional_context)
    )
    conn.execute(
        "UPDATE users SET prds_used_this_month = prds_used_this_month + 1 WHERE id=?",
        (user["id"],)
    )
    conn.commit(); conn.close()
    return JSONResponse({"success": True, "prd_id": prd_id, "content": content, "title": product_name})

@app.get("/api/prd/{prd_id}")
async def get_prd(prd_id: str, request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    conn = get_db()
    prd  = conn.execute("SELECT * FROM prds WHERE id=? AND user_id=?", (prd_id, user["id"])).fetchone()
    conn.close()
    if not prd: raise HTTPException(status_code=404, detail="PRD not found")
    return JSONResponse(dict(prd))

@app.get("/api/prd/{prd_id}/download")
async def download_prd(prd_id: str, request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    conn = get_db()
    prd  = conn.execute("SELECT * FROM prds WHERE id=? AND user_id=?", (prd_id, user["id"])).fetchone()
    conn.close()
    if not prd: raise HTTPException(status_code=404, detail="PRD not found")
    docx_bytes = markdown_to_docx(prd["content"])
    filename   = re.sub(r'[^\w\s-]', '', prd["title"]).strip().replace(' ', '_')
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}_PRD.docx"'}
    )

@app.delete("/api/prd/{prd_id}")
async def delete_prd(prd_id: str, request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    conn = get_db()
    conn.execute("DELETE FROM prds WHERE id=? AND user_id=?", (prd_id, user["id"]))
    conn.commit(); conn.close()
    return JSONResponse({"success": True})

# ─── Stripe API ───────────────────────────────────────────────────────────────
@app.post("/api/create-checkout-session")
async def create_checkout_session(request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            mode="subscription",
            customer_email=user["email"],
            success_url=f"{BASE_URL}/upgrade/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/upgrade",
            metadata={"user_id": user["id"]}
        )
        return JSONResponse({"checkout_url": session.url})
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        return JSONResponse({"error": "Payment setup failed."}, status_code=500)


@app.post("/api/create-yearly-checkout-session")
async def create_yearly_checkout_session(request: Request):
    user = get_current_user(request)
    if not user: return JSONResponse({"error": "Not authenticated"}, status_code=401)
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_YEARLY_PRICE_ID, "quantity": 1}],
            mode="subscription", customer_email=user["email"],
            success_url=f"{BASE_URL}/upgrade/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/upgrade",
            metadata={"user_id": user["id"], "plan": "yearly"}
        )
        return JSONResponse({"checkout_url": session.url})
    except Exception as e:
        logger.error(f"Stripe yearly error: {e}")
        return JSONResponse({"error": "Payment setup failed."}, status_code=500)
@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    if event["type"] == "checkout.session.completed":
        s       = event["data"]["object"]
        user_id = s.get("metadata", {}).get("user_id")
        if user_id:
            conn = get_db()
            conn.execute(
                "UPDATE users SET plan=?, stripe_customer_id=?, stripe_subscription_id=? WHERE id=?",
                (s.get("metadata",{}).get("plan","pro"), s.get("customer"), s.get("subscription"), user_id)
            )
            conn.commit(); conn.close()
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        sub  = event["data"]["object"]
        conn = get_db()
        conn.execute("UPDATE users SET plan='free' WHERE stripe_subscription_id=?", (sub["id"],))
        conn.commit(); conn.close()
    return JSONResponse({"received": True})

# ─── Admin API ────────────────────────────────────────────────────────────────
@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    conn         = get_db()
    total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    pro_users    = conn.execute("SELECT COUNT(*) FROM users WHERE plan='pro'").fetchone()[0]
    total_prds   = conn.execute("SELECT COUNT(*) FROM prds").fetchone()[0]
    recent_users = [dict(r) for r in conn.execute(
        "SELECT id, name, email, plan, role, prds_used_this_month, created_at "
        "FROM users ORDER BY created_at DESC LIMIT 20"
    ).fetchall()]
    recent_prds  = [dict(r) for r in conn.execute(
        "SELECT p.id, p.title, p.created_at, u.email "
        "FROM prds p JOIN users u ON p.user_id=u.id ORDER BY p.created_at DESC LIMIT 20"
    ).fetchall()]
    conn.close()
    return JSONResponse({
        "total_users": total_users, "pro_users": pro_users,
        "total_prds": total_prds,   "mrr": pro_users * 20,
        "users": recent_users,      "prds": recent_prds
    })
