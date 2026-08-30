# Aegis Swarm — Frontend Documentation
Complete documentation of the **Aegis Swarm** frontend: an AI platform for return fraud investigation.
This README describes everything built so far in the frontend so colleagues can understand the structure, pages, auth, data, and MVP limitations.
---
## Overview
Aegis Swarm is a **React SPA** (Single Page Application) that lets investigators:
- Sign in (login / register)
- View a dashboard with KPIs and charts
- Manage investigation lists
- Create a new claim and simulate multi-agent AI analysis
- View details, evidence, AI analysis, and the audit trail
- Make human decisions (approve / reject / manual review)
- View analytics and report on resolved claims
- Configure settings (theme, preferences, AI agents)
> **Important:** There is no real backend. All data is **synthetic** (seed data + in-memory + `localStorage`). Ready for demo / MVP UI.
---
## Tech stack
| Layer | Technology |
|-------|------------|
| UI | React 19 |
| Routing | React Router 8 (`createBrowserRouter`) |
| Charts | Recharts 3 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Build | Vite 8 |
| Language | TypeScript 5.7 (strict) |
| Format | oxfmt |
| Fonts | Inter + JetBrains Mono |
**Path alias:** `@/*` → `./src/*` (configured in Vite + TypeScript)
---
## Running locally

npm install
npm run dev
Server: http://localhost:8443 (or the PORT env variable)
Hot reload is enabled
Scripts:

Command	What it does
npm run dev
Dev server (host 0.0.0.0)
npm run build
Typecheck + production build
npm run preview
Preview the production build
npm run typecheck
TypeScript check only
npm run format
Format with oxfmt
Demo credentials
Email:    investigator@company.com
Password: demo1234
Project structure
src/
├── main.tsx                 # React entrypoint
├── App.tsx                  # AuthProvider + RouterProvider
├── routes.tsx               # All app routes
├── index.css                # Tailwind v4 theme (light/dark)
│
├── pages/                   # Route-level pages
├── layouts/                 # App shell (sidebar + top bar)
├── components/              # Shared UI components
├── hooks/                   # Auth, theme, sidebar, investigations
├── services/                # “API” layer (synthetic, no HTTP)
├── data/                    # Seed / mock data
├── types/                   # TypeScript models
├── utils/                   # Labels, risk helpers, formatters
└── lib/                     # Constants + navigation
Routing & pages
Defined in src/routes.tsx.

Path	Page	Description
/login
Login
Sign in with email/password
/register
Register
Register an investigator (name, email, password, terms)
/
redirect
Redirects to /dashboard
/dashboard
Dashboard
KPI tiles, line chart, risk pie, recent investigations table
/investigations
InvestigationsDashboard
List with search + filters (risk, status, category)
/investigations/new
NewInvestigation
Claim form + staged AI analysis simulation
/investigations/:id
InvestigationDetail
Detail with tabs: Overview / Evidence / AI Analysis / Audit Trail + decision panel
/analytics
Analytics
Time series, risk/recommendation/decision distribution, agent performance table
/reports
Reports
Resolved claims list, preview, export JSON / print PDF
/settings
Settings
Account, theme, notifications, prefs, AI agents
* (inside the app)
redirect
Redirects to /dashboard
/login and /register are public. All other routes sit inside ProtectedRoute → AppLayout.

Layout (App Shell)
src/layouts/AppLayout.tsx

Sidebar (collapsible): Aegis logo, navigation, “Active” status, user avatar/initials, sign-out
Width: 240px / 68px (collapsed)
Collapse state is persisted in localStorage
On mobile: drawer + backdrop
Top bar: hamburger (mobile), page title + breadcrumb, GlobalSearch, notification bell (UI only), theme toggle
Main: <Outlet /> for page content
Navigation (src/lib/navigation.tsx):

Dashboard
Investigations
Analytics & Reports (covers /analytics and /reports)
Settings
Shared components
Component	Role
ProtectedRoute
Blocks access without a session; fullscreen loading; redirect to /login with state.from
GlobalSearch
Search modal with ⌘K / Ctrl+K; debounce; recent claim IDs in localStorage
RiskBadge
Risk badge; also exports StatusBadge, RecommendationBadge, DecisionBadge
LoadingState
Spinner + label (optional fullscreen)
EmptyState
Empty-list UI with optional CTA
There is no src/features/ folder — UI logic lives in pages + components.

Hooks
Hook	File	Purpose
AuthProvider / useAuth
hooks/useAuth.tsx
Session state; login, register, logout
useInvestigations
hooks/useInvestigations.ts
Loads the filtered list
useInvestigation
hooks/useInvestigations.ts
Loads one investigation by id
useSidebar
hooks/useSidebar.ts
Collapse + mobile open (persisted)
useTheme
hooks/useTheme.ts
light / dark / system → .dark class on <html>
Services (“API” layer)
All are async wrappers over seed data / an in-memory store with an artificial delay(). There is no fetch, axios, or backend URL.

Service	Methods / behavior
authApi
getSession, login, register, logout — session in localStorage (aegis-auth-session)
investigationsApi
getAll, getById, search, filter, getRecent, getResolved, updateDecision, create
analyticsApi
Returns static series/KPIs from data/analytics.ts
analysisApi
Simulates multi-stage analysis (~1.4s × 3 stages); heuristic scores from form input
Data models (Types)
Investigation (types/investigation.ts)
The main domain model: claim metadata, risk scores, AI recommendation, status, human decision, agent findings, image metadata, audit trail.

Main unions:

RiskLevel: low | elevated | high | insufficient
InvestigationStatus: pending | resolved | escalated | in_review
AIRecommendation: approve | manual_review | escalate
HumanDecision: approved | rejected | manual_review | null
InvestigationCategory: electronics, clothing, home, sporting, books
User / Auth (types/user.ts)
User, LoginCredentials, RegisterInput, AuthSession

Agents (types/agent.ts)
AgentResult, AgentDefinition, AnalysisStage

Analytics (types/analytics.ts)
TimeSeriesPoint, DistributionItem, DashboardKpi, StatTile

Barrel export: types/index.ts

Seed data (src/data/)
File	Contents
investigations.ts
5 seed claims: CLM-001 … CLM-005 (Laptop, Merino jacket, Headphones, Yoga mat, Smart Watch) — mixed statuses/decisions, Unsplash images, audit trails
users.ts
defaultUser (A. Johnson) + demo credentials
agents.ts
3 MVP agents + 3 roadmap + 3 analysis stages
analytics.ts
Fixed KPIs/charts (activity Aug 4–10, distributions, agent performance)
Utils & Lib
Utils

labels.ts — labels for category/status/recommendation/decision; formatDate, formatCurrency, categoryLabel
risk.ts — getRiskLevel (0 → insufficient; <40 low; <70 elevated; else high) + colors
Lib

constants.ts — APP_NAME, STORAGE_KEYS, MAX_RECENT_SEARCHES
navigation.tsx — NAV_ITEMS, getPageTitle, isNavActive
Auth flow (how it works)
App mounts AuthProvider → reads the session from localStorage via authApi.getSession()
Login: validates only against hard-coded demo credentials; writes { user, token: mock-token-* }
Register: accepts email/password (min 8 characters); creates a user with initials; saves the session (password is not stored)
ProtectedRoute: if loading → spinner; if no session → /login with from; after login redirects to from or /dashboard
Logout: clears the session from the sidebar
The session is client-side only. The mock token is not used for API calls.

Main UI features
Dashboard
4 KPI tiles
Line chart (activity) + pie chart (risk) with Recharts
Recent investigations table
CTA for a new investigation
Investigations list
Search + filters (risk, status, category)
Click a row → detail page
New Investigation
Claim ID (auto), category, order value, explanation (≥20 chars)
Optional image drag/drop
Staged AI agent animation → create → navigate to detail
Investigation Detail
Score ring, agent summary
Evidence image + metadata
Orchestrator breakdown
Human decision panel: approve / manual review / reject + notes
Audit timeline
Analytics
Date/category filters (UI; filters are not fully wired to the data)
Multi-chart + agent performance table
Reports
Select a resolved claim
Preview
Export JSON or window.print() as PDF
Settings
Theme works for real (light/dark/system)
Account / notifications / prefs are mostly local UI (no backend)
AI agents: active MVP vs roadmap
Other
Global search with recent history
Light / dark / system theme
Persisted sidebar collapse
AI agents (product story)
MVP (active in the UI):

Visual Evidence
Claim Intelligence
Orchestrator
Roadmap (shown as coming soon):

Shipment
Marketplace
Threat Intelligence
“AI” analysis is a UI simulation (staged delays + heuristic scores). The name “Amazon Nova Pro” appears in copy only, not as a real integration.

Styling & theme
src/index.css — Tailwind v4 @theme inline with CSS variables.

Mode	Background	Primary
Light (:root)
#F8FAFC
#2563EB
Dark (.dark)
#0B1120
#3B82F6
Also: Inter for body, JetBrains Mono for .font-mono, thin scrollbars, focus-visible rings.

What is real vs synthetic (MVP)
Area	Current reality
Auth
Synthetic; login only with demo credentials; register = local session
Investigations
Seed + in-memory mutate (lost on full refresh)
AI analysis
Timed stages + heuristic scores
Analytics / KPI
Static numbers from seed (not computed from the store)
Settings / account save
Mostly UI (theme + sidebar + auth session + recent searches persist)
Notifications bell
Decorative
Reports PDF
Browser print
Network / backend
None
Code conventions (for colleagues)
Strings with apostrophes → double quotes
Page components → default export
Business logic → hooks / services, not inline in JSX
Styling → Tailwind utility classes; global theme in index.css
Imports → use the @/... alias
Typical user flow (demo)
Open /login → sign in with investigator@company.com / demo1234
View Dashboard (KPI + charts + recent claims)
Go to Investigations → filter / search
Open a claim (e.g. CLM-001) → view Overview / Evidence / AI / Audit
Make a human decision (approve / reject / manual review)
Or create a new claim at New Investigation and follow the staged AI analysis
View Analytics and Reports (export JSON / print)
Change the theme in Settings
Pages and features
Dashboard (/dashboard)
The main page after login. Shows:

Personalized greeting with the user’s name
4 KPI cards: Total Investigations (124), Pending Review (18), High Risk (12), Reviewed (94) — with trends
Activity chart (LineChart): total vs resolved over 7 days
Risk distribution chart (donut PieChart): Low, Elevated, High, Insufficient
Table of the 4 most recent investigations with Claim ID, product, date, risk badge, status, and a “Review” link
“New Investigation” button that goes to create flow
Investigations Dashboard (/investigations)
Full investigation list with:

Text search by Claim ID, product, category, status
Filters: Risk (Low/Elevated/High), Status (Pending/In Review/Resolved/Escalated), Category (Electronics/Clothing/Sporting)
Real-time result count
Detailed table with: Claim ID, product + value, category, date, risk score, AI recommendation, human decision, status, last updated
Clicking a row navigates to details
Empty state when there are no results
Button to create a new investigation
Investigation Detail (/investigations/:id)
The richest page in the app, with 4 tabs:

Overview tab:

Visual risk score ring (0–100) with colors (green/yellow/red)
AI recommendation (Approve / Manual Review / Escalate) with a warning that the final decision is human
Key Findings — up to 4 findings from AI agents
Agent Summary — Visual Evidence Agent, Claim Intelligence Agent, Orchestrator with score, confidence, status
Sidebar Human Investigator Decision panel:
3 options: Approve Refund, Manual Review, Reject Refund
Notes field for rationale
“Save Decision” button that updates the investigation and audit trail
Evidence tab:

Shows the evidence photo (if present) or an “Insufficient Data” message
File metadata: type, resolution, EXIF, editing software, GPS, timestamp
Signals detected by the Visual Evidence Agent
AI Analysis tab:

Agent 1 — Visual Evidence Agent: risk score, confidence, manipulation status, metadata findings, agent explanation
Agent 3 — Claim Intelligence Agent: analysis of the customer explanation, detected patterns, explanation
Agent 6 — Orchestrator: combines evidence with 50/50 weights, overall risk score, final summary
Audit Trail tab:

Chronological event timeline: System, Privacy Guard, Storage, AI agents, Investigator
Each event has time, component, description, status (success/warning/info), AI model
New Investigation (/investigations/new)
3-step form to create a new investigation:

Step 1 — Claim Details:

Claim ID (auto-generated, readonly)
Product category (Electronics, Clothing, Home & Garden, Sporting Goods, Books & Media)
Order value ($)
Step 2 — Customer Explanation:

Textarea for the customer explanation (min 20 characters, with character count)
Step 3 — Visual Evidence:

Image upload via drag & drop or click (JPEG/PNG)
Image preview with a remove option
Optional — analysis still runs without an image
After submit:

“Analyzing Investigation” screen with 3 animated stages:
Visual Evidence Agent
Claim Intelligence Agent
Orchestrator
Each stage lasts ~1.4 seconds (simulation)
When finished, the new investigation is created and the user is redirected to the detail page
Privacy Protection: message that PII is automatically removed before AI processing.

Analytics (/analytics)
Analytics dashboard with:

4 stat tiles: Avg Risk Score (61), AI Accuracy (85%), Avg Processing (1.2s), Agreement Rate (79%)
Investigations Over Time chart (3 lines: Total, Resolved, High Risk)
3 distribution charts: Risk (pie), AI Recommendation (bar), Human Decision (bar)
Agent Performance table: Visual Evidence, Claim Intel, Orchestrator — with agreement rate, avg score, avg confidence
Date filters (7d/30d/90d) and category (UI only; they do not currently filter the data)
Link to Reports
Reports (/reports)
Reports for completed investigations:

Table of investigations with status resolved or with a human decision
Clicking selects the report and shows a sidebar with:
Investigation summary
Overall risk score
AI recommendation
Export: JSON (file download) or PDF (window.print)
“Export All (JSON)” button for all reports
Link to Analytics
Settings (/settings)
Configuration split into sections:

Account: avatar with initials, name, email, password change (UI only, not persisted)
Appearance: light / dark / system theme
Notifications: toggles for high-risk alerts, investigation completed, human review required
Investigation Preferences: auto-assign, require decision notes, high-risk threshold slider (50–95)
AI Configuration: model (Amazon Nova Pro), human-in-the-loop, agent weights (50/50), PII removal
List of active agents (3 MVP)
List of roadmap agents (3 upcoming)
Security & Privacy: PII protection, audit logging, human oversight
Most settings are UI-only — they are not saved to storage.

AI Agent System
Active agents (MVP)
Visual Evidence Agent — analyzes uploaded images for manipulation and authenticity (EXIF metadata, editing software, damage patterns)
Claim Intelligence Agent — analyzes the customer explanation for fraud signals (urgent language, timeline mismatches, similarity to known patterns)
Orchestrator Agent — combines agent outputs with equal weights (50/50) for the final risk score and recommendation
Roadmap agents (not implemented)
Shipment Verification Agent — carrier tracking verification
Marketplace Intelligence Agent — cross-reference marketplace history
Threat Intelligence Agent — match against fraud syndicate patterns
Analysis logic (simulation)
When a new investigation is created, analysisApi.runAnalysis():

Runs 3 stages with a 1.4s delay each
Generates scores from input:
With image: visual score 55–85, claim score 40–75, risk = 50/50 average
Without image: claim score only, visual = 0
Recommendation: < 35 = Approve, 35–74 = Manual Review, ≥ 75 = Escalate
Model referenced in the UI: Amazon Nova Pro v1.0 (simulation, not a real integration).

Risk levels
Score	Level
0
Insufficient Data (no image)
1–39
Low Risk (green)
40–69
Elevated (yellow/amber)
70–100
High Risk (red)
Synthetic data (Seed Data)
5 starter investigations
Claim ID	Product	Category	Risk	Status	AI recommendation	Human decision
CLM-001
Laptop Pro 16"
Electronics
72 (Elevated)
Pending
Manual Review
—
CLM-002
Merino Wool Jacket
Clothing
24 (Low)
Resolved
Approve
Approved
CLM-003
Headphones Elite
Electronics
91 (High)
Pending
Escalate
—
CLM-004
Yoga Mat Pro
Sporting
38 (Low)
In Review
Manual Review
— (no image)
CLM-005
Smart Watch Series 9
Electronics
61 (Elevated)
Resolved
Manual Review
Rejected
Each investigation has: customer explanation, score/confidence per agent, findings, image metadata, audit trail, summary, notes.

Analytics data
KPIs, activity charts, risk/recommendation/decision distributions, agent performance — all static in src/data/analytics.ts.

In-memory store
investigationsApi keeps an in-memory array (let store). New investigations are prepended. Human decisions update the store. Data resets on page refresh.

Suggested next steps (backend integration)
When connecting a real API:

Replace services/* with fetch/axios against backend endpoints
Auth with a real JWT/cookie (not a localStorage mock token)
Persist investigations / decisions in a DB
Real AI analysis (instead of the analysisApi simulation)
Analytics computed from real data
Image upload to storage (S3, etc.)
Author / status
Frontend MVP built to demo the Aegis Swarm — AI Investigation Platform.

If you have questions about structure, start with:

src/routes.tsx — page map
src/services/ — how data “arrives”
src/types/ — domain contracts
src/data/ — demo seed
