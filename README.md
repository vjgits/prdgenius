# ✦ PRDGenius — AI-Powered PRD Generator

> Generate professional Product Requirements Documents in seconds using Claude AI.

![PRDGenius](https://img.shields.io/badge/Powered%20by-Claude%20AI-818cf8?style=flat-square&logo=anthropic)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)
![Stripe](https://img.shields.io/badge/Payments-Stripe-6772e5?style=flat-square&logo=stripe)
![Railway](https://img.shields.io/badge/Hosted%20on-Railway-0B0D0E?style=flat-square&logo=railway)

---

## What is PRDGenius?

PRDGenius is a full-stack SaaS application that uses Anthropic's Claude AI to generate structured, investor-ready Product Requirements Documents from a simple feature description and problem statement.

Built as a solo end-to-end project — from ideation to production deployment — as a showcase of full-stack product engineering.

---

## Features

- **AI-Powered PRD Generation** — Leverages Claude Sonnet to produce detailed PRDs with user stories, acceptance criteria, success metrics, and technical considerations
- **Authentication** — Secure signup/login with session-based auth and bcrypt password hashing
- **Freemium Model** — Free tier (1 PRD), Pro plan ($20/month via Stripe), unlimited admin role
- **Download Options** — Export as Word (.docx) or browser PDF
- **Public Share Links** — Share any PRD via a unique URL
- **Admin Dashboard** — Real-time stats: total users, MRR, recent PRDs
- **Security Hardened** — Rate limiting, security headers (HSTS, CSP, XFO), input validation, WAL-mode SQLite

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python) |
| **AI** | Anthropic Claude (`claude-sonnet-4-6`) |
| **Database** | SQLite (WAL mode) |
| **Auth** | Session tokens + bcrypt |
| **Payments** | Stripe Checkout + Webhooks |
| **Frontend** | Vanilla JS + Jinja2 templates |
| **Hosting** | Railway |
| **Docs Export** | python-docx |

---

## Running Locally

### 1. Clone & install

```bash
git clone https://github.com/vjgitxx/prdgenius.git
cd prdgenius
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set environment variables

Create a `.env` file:

```env
ANTHROPIC_API_KEY=your_anthropic_key
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
BASE_URL=http://localhost:8000
PASSWORD_SALT=any-random-32-char-string
```

### 3. Run

```bash
uvicorn main:app --reload
```

Visit [http://localhost:8000](http://localhost:8000)

---

## Deployment (Railway)

1. Push to GitHub
2. Create new Railway project → Deploy from GitHub repo
3. Set environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY`
   - `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`
   - `BASE_URL` = your Railway domain (e.g. `https://prdgenius.up.railway.app`)
   - `PRODUCTION=true`
   - `PASSWORD_SALT` = a random 32+ character string
4. Railway auto-detects `railway.toml` and uses `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set Stripe webhook endpoint to `https://your-domain/stripe/webhook`

---

## Project Structure

```
prdgenius/
├── main.py              # FastAPI app — routes, DB, auth, Stripe
├── prd_prompt.py        # Claude AI prompt engineering
├── requirements.txt
├── railway.toml         # Railway deployment config
├── templates/
│   ├── landing.html     # Marketing landing page
│   ├── login.html
│   ├── signup.html
│   ├── app.html         # Main PRD generator UI
│   ├── prd_view.html    # Public PRD share page
│   ├── upgrade.html     # Stripe checkout page
│   ├── upgrade_success.html
│   └── admin.html       # Admin dashboard
└── static/              # CSS, JS, assets
```

---

## Security

- Passwords hashed with bcrypt + salt
- Rate limiting on auth endpoints (10 login attempts / 10 min per IP)
- Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`
- CORS restricted to production domain
- Pydantic input validation with strict length limits
- Stripe webhook signature verification
- Session tokens with expiry

---

## License

MIT — feel free to fork and build on this.

---

*Built by [Vijay Suresh](https://linkedin.com/in/vijaysuresh) · Powered by Claude AI · Deployed on Railway*
