# ✦ PRDGenius — AI-Powered PRD Generator

> Generate professional Product Requirements Documents in seconds using Claude AI.

![PRDGenius](https://img.shields.io/badge/Powered%20by-Claude%20AI-818cf8?style=flat-square&logo=anthropic)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)
![Stripe](https://img.shields.io/badge/Payments-Stripe-6772e5?style=flat-square&logo=stripe)
![Railway](https://img.shields.io/badge/Hosted%20on-Railway-0B0D0E?style=flat-square&logo=railway)

---

## What is PRDGenius?

PRDGenius is a full-stack SaaS application that uses Anthropic's Claude AI to generate structured, FAANG-quality Product Requirements Documents from a simple feature description and problem statement.

Built as a solo end-to-end project — from ideation to production deployment — as a showcase of full-stack product and software engineering.

Live at: **[prdgenius.up.railway.app](https://prdgenius.up.railway.app)**

---

## Features

- **AI-Powered PRD Generation** — Claude `claude-sonnet-4-6` produces complete PRDs with user stories, acceptance criteria, success metrics, feature prioritization (P0/P1/P2), technical considerations, timeline, and risk analysis
- **PRD Size Selector** — Choose Brief (essentials only), Medium (balanced), or Extensive (deep & detailed)
- **3 PRD Formats** — Google Style (full spec), Amazon Working Backwards (Press Release + FAQ), Linear Style (concise)
- **Edit & Regenerate** — Go back, tweak inputs, and regenerate without starting over
- **Light / Dark Mode** — Toggle with persistent preference saved to localStorage
- **Authentication** — Secure signup/login with session-based auth and bcrypt password hashing
- **Freemium Model** — Free tier (1 PRD/month), Pro Monthly ($9.99/month), Pro Yearly ($99/year) via Stripe Checkout
- **Download Options** — Export as Word (.docx) or browser PDF
- **Public Share Links** — Share any PRD via a unique URL
- **Admin Dashboard** — Real-time stats: total users, MRR, recent PRDs
- **Security Hardened** — IP-based rate limiting, email domain validation, security headers (HSTS, CSP, XFO), input validation, WAL-mode SQLite with Railway Volume persistence

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python), async/await throughout |
| **AI** | Anthropic Claude (`claude-sonnet-4-6`) with async continuation loop |
| **Database** | SQLite (WAL mode) on Railway persistent Volume |
| **Auth** | Session tokens + bcrypt |
| **Payments** | Stripe Checkout + Webhooks (monthly + yearly plans) |
| **Frontend** | Vanilla JS + Tailwind CSS + Jinja2 templates |
| **Hosting** | Railway (with persistent volume at `/data`) |
| **Docs Export** | python-docx |

---

## Running Locally

### 1. Clone & install

```bash
git clone https://github.com/vjgits/prdgenius.git
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
STRIPE_PRICE_ID=price_...           # Monthly plan price ID
STRIPE_YEARLY_PRICE_ID=price_...    # Yearly plan price ID
BASE_URL=http://localhost:8000
PASSWORD_SALT=any-random-32-char-string
DB_PATH=./prd_genius.db             # Local DB path (Railway uses /data/prd_genius.db)
```

### 3. Run

```bash
uvicorn main:app --reload
```

Visit [http://localhost:8000](http://localhost:8000)

---

## Deployment (Railway)

1. Push to GitHub
2. Connect repo to Railway project
3. Add a **Volume** mounted at `/data` for SQLite persistence
4. Set environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY`
   - `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
   - `STRIPE_PRICE_ID` (monthly), `STRIPE_YEARLY_PRICE_ID` (yearly)
   - `BASE_URL` = your Railway domain (e.g. `https://prdgenius.up.railway.app`)
   - `PRODUCTION=true`
   - `PASSWORD_SALT` = a random 32+ character string
   - `DB_PATH=/data/prd_genius.db`
5. Set Stripe webhook endpoint to `https://your-domain/stripe/webhook`

---

## Project Structure

```
prdgenius/
├── main.py                  # FastAPI app — routes, DB, auth, Stripe, AI generation
├── requirements.txt
├── railway.toml             # Railway deployment config
└── templates/
    ├── landing.html         # Marketing landing page
    ├── login.html
    ├── signup.html
    ├── app.html             # Main PRD generator UI (dark/light mode, size selector)
    ├── prd_view.html        # Public PRD share page
    ├── upgrade.html         # Stripe checkout (monthly + yearly toggle)
    ├── upgrade_success.html
    └── admin.html           # Admin dashboard
```

---

## Security

- Passwords hashed with bcrypt + salt
- IP-based rate limiting: 3 signups / 10 min, 10 logins / 5 min, 5 generations / min
- Email domain validation (blocks disposable/throwaway emails)
- Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Referrer-Policy`
- CORS restricted to production domain
- Stripe webhook signature verification
- Session tokens with expiry
- SQLite WAL mode with Railway persistent Volume

---

## Pricing

| Plan | Price | PRDs |
|------|-------|------|
| Free | $0 | 1 PRD / month |
| Pro Monthly | $9.99 / month | 100 PRDs / month |
| Pro Yearly | $99 / year | 100 PRDs / month |

---

## License

MIT — feel free to fork and build on this.

---

*Built by [Vijay Suresh](https://linkedin.com/in/vijaysuresh) · Powered by Claude AI · Deployed on Railway*
