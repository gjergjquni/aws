# Aegis Swarm — Frontend Documentation

Dokumentim i plotë i aplikacionit frontend të **Aegis Swarm**: platformë AI për hetimin e mashtrimeve në kthime (return fraud investigation).

Ky README përshkruan gjithçka që është ndërtuar deri tani në frontend, që kolegët të kuptojnë strukturën, faqet, auth-in, të dhënat dhe kufizimet e MVP-së.

---

## Përmbledhje

Aegis Swarm është një **React SPA** (Single Page Application) që lejon investigatorët të:

- Hyjnë në sistem (login / register)
- Shohin dashboard me KPI dhe grafikë
- Menaxhojnë lista hetimesh (investigations)
- Krijojnë claim të ri dhe të simulojnë analizë AI me shumë agjentë
- Shohin detaje, evidence, AI analysis dhe audit trail
- Marrin vendime njerëzore (approve / reject / manual review)
- Shikojnë analytics dhe raportojnë claim-e të zgjidhura
- Konfigurojnë settings (theme, preferenca, AI agents)

> **E rëndësishme:** Nuk ka backend real. Të gjitha të dhënat janë **sintetike** (seed data + in-memory + `localStorage`). Gati për demo / MVP UI.

---

## Stack teknologjik

| Shtresa | Teknologjia |
|--------|-------------|
| UI | React 19 |
| Routing | React Router 8 (`createBrowserRouter`) |
| Grafikë | Recharts 3 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) |
| Build | Vite 8 |
| Language | TypeScript 5.7 (strict) |
| Format | oxfmt |
| Fonts | Inter + JetBrains Mono |

**Path alias:** `@/*` → `./src/*` (konfiguruar në Vite + TypeScript)

---

## Si ta nisësh lokalisht

```bash
npm install
npm run dev
```

- Serveri: `http://localhost:8443` (ose `PORT` env)
- Hot reload aktiv

**Skriptet:**

| Komanda | Çfarë bën |
|---------|-----------|
| `npm run dev` | Dev server (host `0.0.0.0`) |
| `npm run build` | Typecheck + production build |
| `npm run preview` | Preview i build-it |
| `npm run typecheck` | Vetëm TypeScript check |
| `npm run format` | Formatim me oxfmt |

### Kredencialet demo

```
Email:    investigator@company.com
Password: demo1234
```

---

## Struktura e projektit

```
src/
├── main.tsx                 # Entrypoint React
├── App.tsx                  # AuthProvider + RouterProvider
├── routes.tsx               # Të gjitha rrugët e app-it
├── index.css                # Tema Tailwind v4 (light/dark)
│
├── pages/                   # Faqet e rrugëve
├── layouts/                 # App shell (sidebar + topbar)
├── components/              # Komponente të përbashkëta UI
├── hooks/                   # Auth, theme, sidebar, investigations
├── services/                # “API” layer (sintetik, pa HTTP)
├── data/                    # Seed / mock data
├── types/                   # Modelet TypeScript
├── utils/                   # Labels, risk helpers, formatters
└── lib/                     # Constants + navigation
```

---

## Routing & faqet

Definuara në `src/routes.tsx`.

| Path | Faqja | Përshkrim |
|------|-------|-----------|
| `/login` | `Login` | Hyrje me email/password |
| `/register` | `Register` | Regjistrim investigator (emër, email, password, terms) |
| `/` | redirect | Ridrejton te `/dashboard` |
| `/dashboard` | `Dashboard` | KPI tiles, line chart, pie risk, tabela e hetimeve të fundit |
| `/investigations` | `InvestigationsDashboard` | Lista me search + filtra (risk, status, kategori) |
| `/investigations/new` | `NewInvestigation` | Formë claim + simulim analize AI me stages |
| `/investigations/:id` | `InvestigationDetail` | Detaje me tabs: Overview / Evidence / AI Analysis / Audit Trail + panel vendimi |
| `/analytics` | `Analytics` | Time series, shpërndarje risk/rec/decision, tabela e performancës së agjentëve |
| `/reports` | `Reports` | Lista e claim-eve të zgjidhura, preview, export JSON / print PDF |
| `/settings` | `Settings` | Account, theme, notifications, prefs, AI agents |
| `*` (brenda app) | redirect | Ridrejton te `/dashboard` |

Rrugët `/login` dhe `/register` janë publike. Të gjitha të tjerat janë brenda `ProtectedRoute` → `AppLayout`.

---

## Layout (App Shell)

**`src/layouts/AppLayout.tsx`**

- **Sidebar (collapsible):** logo Aegis, navigim, status “Active”, avatar/initials i user-it, sign-out
  - Gjerësia: 240px / 68px (collapsed)
  - Collapse ruhet në `localStorage`
  - Në mobile: drawer + backdrop
- **Top bar:** hamburger (mobile), titulli i faqes + breadcrumb, `GlobalSearch`, bell njoftime (vetëm UI), theme toggle
- **Main:** `<Outlet />` për përmbajtjen e faqes

**Navigimi** (`src/lib/navigation.tsx`):

1. Dashboard
2. Investigations
3. Analytics & Reports (mbulon `/analytics` dhe `/reports`)
4. Settings

---

## Komponentet e përbashkëta

| Komponent | Roli |
|-----------|------|
| `ProtectedRoute` | Bllokon aksesin pa session; loading fullscreen; ridrejtim te `/login` me `state.from` |
| `GlobalSearch` | Modal search me ⌘K / Ctrl+K; debounce; recent claim IDs në `localStorage` |
| `RiskBadge` | Badge për risk; eksporton edhe `StatusBadge`, `RecommendationBadge`, `DecisionBadge` |
| `LoadingState` | Spinner + label (opsional fullscreen) |
| `EmptyState` | UI për lista bosh me CTA opsional |

Nuk ka folder `src/features/` — logjika e UI është në pages + components.

---

## Hooks

| Hook | File | Funksioni |
|------|------|-----------|
| `AuthProvider` / `useAuth` | `hooks/useAuth.tsx` | Session state; `login`, `register`, `logout` |
| `useInvestigations` | `hooks/useInvestigations.ts` | Ngarkon listën e filtruar |
| `useInvestigation` | `hooks/useInvestigations.ts` | Ngarkon një investigation sipas `id` |
| `useSidebar` | `hooks/useSidebar.ts` | Collapse + mobile open (persist) |
| `useTheme` | `hooks/useTheme.ts` | `light` / `dark` / `system` → class `.dark` në `<html>` |

---

## Services (shtresa “API”)

Të gjitha janë async wrappers mbi seed data / in-memory store me `delay()` artificial. **Nuk ka `fetch`, axios, as URL backend.**

| Service | Metodat / sjellja |
|---------|-------------------|
| `authApi` | `getSession`, `login`, `register`, `logout` — session në `localStorage` (`aegis-auth-session`) |
| `investigationsApi` | `getAll`, `getById`, `search`, `filter`, `getRecent`, `getResolved`, `updateDecision`, `create` |
| `analyticsApi` | Kthen seritë/KPI statike nga `data/analytics.ts` |
| `analysisApi` | Simulon analizë multi-stage (~1.4s × 3 stages); skorë heuristike nga form input |

---

## Modelet e të dhënave (Types)

### Investigation (`types/investigation.ts`)

Modeli kryesor i domain-it: metadata e claim-it, risk scores, AI recommendation, status, human decision, agent findings, image metadata, audit trail.

**Unions kryesore:**

- `RiskLevel`: `low` | `elevated` | `high` | `insufficient`
- `InvestigationStatus`: `pending` | `resolved` | `escalated` | `in_review`
- `AIRecommendation`: `approve` | `manual_review` | `escalate`
- `HumanDecision`: `approved` | `rejected` | `manual_review` | `null`
- `InvestigationCategory`: electronics, clothing, home, sporting, books

### User / Auth (`types/user.ts`)

`User`, `LoginCredentials`, `RegisterInput`, `AuthSession`

### Agents (`types/agent.ts`)

`AgentResult`, `AgentDefinition`, `AnalysisStage`

### Analytics (`types/analytics.ts`)

`TimeSeriesPoint`, `DistributionItem`, `DashboardKpi`, `StatTile`

Barrel export: `types/index.ts`

---

## Seed data (`src/data/`)

| File | Përmbajtja |
|------|------------|
| `investigations.ts` | 5 claim seed: **CLM-001 … CLM-005** (Laptop, Merino jacket, Headphones, Yoga mat, Smart Watch) — statuse/vendime të ndryshme, imazhe Unsplash, audit trails |
| `users.ts` | `defaultUser` (A. Johnson) + demo credentials |
| `agents.ts` | 3 agjentë MVP + 3 roadmap + 3 analysis stages |
| `analytics.ts` | KPI/chart të fiksuara (aktivitet Aug 4–10, shpërndarje, performancë agjentësh) |

---

## Utils & Lib

**Utils**

- `labels.ts` — labels për kategori/status/recommendation/decision; `formatDate`, `formatCurrency`, `categoryLabel`
- `risk.ts` — `getRiskLevel` (0 → insufficient; &lt;40 low; &lt;70 elevated; else high) + ngjyra

**Lib**

- `constants.ts` — `APP_NAME`, `STORAGE_KEYS`, `MAX_RECENT_SEARCHES`
- `navigation.tsx` — `NAV_ITEMS`, `getPageTitle`, `isNavActive`

---

## Auth flow (si funksionon)

1. `App` mounton `AuthProvider` → lexon session nga `localStorage` me `authApi.getSession()`
2. **Login:** validon vetëm kundër kredencialeve demo hard-coded; shkruan `{ user, token: mock-token-* }`
3. **Register:** pranon email/password (min 8 karakterë); krijon user me initials; ruan session (password nuk ruhet)
4. **ProtectedRoute:** nëse loading → spinner; nëse pa session → `/login` me `from`; pas login ridrejton te `from` ose `/dashboard`
5. **Logout:** pastron session nga sidebar

Session është **vetëm client-side**. Token-i mock nuk përdoret për API calls.

---

## Features kryesore të UI

### Dashboard
- 4 KPI tiles
- Line chart (aktivitet) + pie chart (risk) me Recharts
- Tabela e hetimeve të fundit
- CTA për investigation të re

### Investigations list
- Search + filtra (risk, status, kategori)
- Klik në rresht → detail page

### New Investigation
- Claim ID (auto), kategori, order value, explanation (≥20 chars)
- Image drag/drop opsional
- Animacion staged i agjentëve AI → `create` → navigim te detail

### Investigation Detail
- Score ring, përmbledhje agjentësh
- Evidence image + metadata
- Breakdown i Orchestrator-it
- Panel vendimi njerëzor: approve / manual review / reject + notes
- Audit timeline

### Analytics
- Filtra date/kategori (UI; filtrat nuk janë të lidhur plotësisht me data)
- Multi-chart + tabela e performancës së agjentëve

### Reports
- Zgjedh claim të zgjidhur
- Preview
- Export JSON ose `window.print()` si PDF

### Settings
- Theme funksionon realisht (light/dark/system)
- Account / notifications / prefs janë kryesisht UI lokale (pa backend)
- AI agents: MVP aktivë vs roadmap

### Të tjera
- Global search me histori të fundit
- Theme light / dark / system
- Sidebar collapse i persistuar

---

## Agjentët AI (story produkti)

**MVP (aktive në UI):**

1. Visual Evidence
2. Claim Intelligence
3. Orchestrator

**Roadmap (të shfaqura si coming soon):**

- Shipment
- Marketplace
- Threat Intelligence

Analiza “AI” është **simulim UI** (stages me delay + skorë heuristike). Emri “Amazon Nova Pro” shfaqet vetëm në copy, jo si integrim real.

---

## Styling & tema

`src/index.css` — Tailwind v4 `@theme inline` me CSS variables.

| Mode | Background | Primary |
|------|------------|---------|
| Light (`:root`) | `#F8FAFC` | `#2563EB` |
| Dark (`.dark`) | `#0B1120` | `#3B82F6` |

Gjithashtu: Inter për body, JetBrains Mono për `.font-mono`, scrollbar të hollë, focus-visible rings.

---

## Çfarë është reale vs sintetike (MVP)

| Zona | Realiteti aktual |
|------|------------------|
| Auth | Sintetik; login vetëm me demo credentials; register = session lokale |
| Investigations | Seed + mutate in-memory (humbet në full refresh) |
| AI analysis | Timed stages + skorë heuristike |
| Analytics / KPI | Numra statikë nga seed (jo të llogaritur nga store) |
| Settings / account save | Kryesisht UI (theme + sidebar + auth session + recent searches persistojnë) |
| Notifications bell | Dekorativ |
| Reports PDF | Browser print |
| Network / backend | **Nuk ka** |

---

## Konventa të kodit (për kolegët)

- Stringjet me apostrof → double quotes
- Page components → **default export**
- Business logic → hooks / services, jo inline në JSX
- Styling → Tailwind utility classes; tema globale në `index.css`
- Importet → përdor alias `@/...`

---

## Flow tipik i përdoruesit (demo)

1. Hap `/login` → hyr me `investigator@company.com` / `demo1234`
2. Shiko **Dashboard** (KPI + grafikë + recent claims)
3. Shko te **Investigations** → filtro / kërko
4. Hap një claim (p.sh. CLM-001) → shiko Overview / Evidence / AI / Audit
5. Merr vendim njerëzor (approve / reject / manual review)
6. Ose krijo claim të ri te **New Investigation** dhe ndiq staged AI analysis
7. Shiko **Analytics** dhe **Reports** (export JSON / print)
8. Ndrysho theme te **Settings**

---

## Hapat e ardhshëm (sugjeruar për backend integration)

Kur të lidhet me API real:

1. Zëvendëso `services/*` me `fetch`/`axios` drejt backend endpoints
2. Auth me JWT/cookie reale (jo `localStorage` mock token)
3. Persistenca e investigations / decisions në DB
4. AI analysis reale (në vend të `analysisApi` simulimit)
5. Analytics të llogaritura nga të dhëna reale
6. Upload imazhesh në storage (S3 etj.)

---

## Autor / status

Frontend MVP i ndërtuar për demo të platformës **Aegis Swarm — AI Investigation Platform**.

Nëse ke pyetje mbi strukturën, shiko fillimisht:

- `src/routes.tsx` — harta e faqeve
- `src/services/` — si “vijnë” të dhënat
- `src/types/` — kontrata e domain-it
- `src/data/` — seed për demo


5. Faqet dhe Funksionalitetet
5.1 Dashboard (/dashboard)
Faqja kryesore pas login-it. Shfaq:

Përshëndetje personalizuar me emrin e përdoruesit
4 KPI karta: Total Investigations (124), Pending Review (18), High Risk (12), Reviewed (94) — me trende
Grafik aktiviteti (LineChart): total vs resolved gjatë 7 ditëve
Grafik shpërndarje risku (PieChart donut): Low, Elevated, High, Insufficient
Tabela e 4 hetimit të fundit me Claim ID, produkt, datë, risk badge, status, link "Review"
Buton "New Investigation" që çon te krijimi i ri
5.2 Investigations Dashboard (/investigations)
Lista e plotë e hetimit me:

Kërkim tekst sipas Claim ID, produktit, kategorisë, statusit
Filtra: Risk (Low/Elevated/High), Status (Pending/In Review/Resolved/Escalated), Category (Electronics/Clothing/Sporting)
Numërim rezultatesh në kohë reale
Tabelë e detajuar me: Claim ID, produkt + vlera, kategori, datë, risk score, rekomandim AI, vendim njerëzor, status, data e përditësimit
Klikimi në rresht navigon te detajet
Empty state kur nuk ka rezultate
Buton për krijim hetimi të ri
5.3 Investigation Detail (/investigations/:id)
Faqja më e pasur e aplikacionit, me 4 tabs:

Tab Overview:

Unazë vizuale e risk score (0–100) me ngjyra (jeshile/verdhë/kuqe)
Rekomandimi AI (Approve / Manual Review / Escalate) me paralajmërim që vendimi final është njerëzor
Key Findings — deri në 4 gjetje nga agjentët AI
Agent Summary — Visual Evidence Agent, Claim Intelligence Agent, Orchestrator me score, confidence, status
Panel anësor Human Investigator Decision:
3 opsione: Approve Refund, Manual Review, Reject Refund
Fushë notes për arsyetim
Buton "Save Decision" që përditëson hetimin dhe audit trail
Tab Evidence:

Shfaq foton e provës (nëse ekziston) ose mesazh "Insufficient Data"
Metadata e skedarit: lloji, rezolucioni, EXIF, software editimi, GPS, timestamp
Sinjalet e detektuara nga Visual Evidence Agent
Tab AI Analysis:

Agent 1 — Visual Evidence Agent: risk score, confidence, manipulation status, metadata findings, shpjegim i agjentit
Agent 3 — Claim Intelligence Agent: analizë e shpjegimit të klientit, pattern të detektuara, shpjegim
Agent 6 — Orchestrator: kombinim i provave me pesha 50/50, overall risk score, përmbledhje finale
Tab Audit Trail:

Timeline kronologjik i ngjarjeve: System, Privacy Guard, Storage, agjentët AI, Investigator
Çdo event ka kohë, komponent, përshkrim, status (success/warning/info), model AI
5.4 New Investigation (/investigations/new)
Formë me 3 hapa për krijim hetimi të ri:

Hapi 1 — Claim Details:

Claim ID (auto-gjeneruar, readonly)
Kategoria e produktit (Electronics, Clothing, Home & Garden, Sporting Goods, Books & Media)
Vlera e porosisë ($)
Hapi 2 — Customer Explanation:

Textarea për shpjegimin e klientit (min 20 karaktere, me numërim karakteresh)
Hapi 3 — Visual Evidence:

Upload imazhi me drag & drop ose klik (JPEG/PNG)
Preview i imazhit me opsion heqjeje
Opsionale — analiza funksionon edhe pa imazh
Pas submit:

Ekran "Analyzing Investigation" me 3 faza të animuara:
Visual Evidence Agent
Claim Intelligence Agent
Orchestrator
Çdo fazë zgjat ~1.4 sekonda (simulim)
Pas përfundimit, krijohet hetimi i ri dhe ridrejtohet te faqja e detajeve
Privacy Protection: mesazh që PII hiqet automatikisht para procesimit AI.

5.5 Analytics (/analytics)
Dashboard analitik me:

4 stat tiles: Avg Risk Score (61), AI Accuracy (85%), Avg Processing (1.2s), Agreement Rate (79%)
Grafik Investigations Over Time (3 linja: Total, Resolved, High Risk)
3 grafikë shpërndarjeje: Risk (pie), AI Recommendation (bar), Human Decision (bar)
Tabelë Agent Performance: Visual Evidence, Claim Intel, Orchestrator — me agreement rate, avg score, avg confidence
Filtra datash (7d/30d/90d) dhe kategori (UI only, nuk filtrojnë të dhënat aktualisht)
Link te Reports
5.6 Reports (/reports)
Raportet e hetimit të përfunduar:

Tabelë e hetimit me status resolved ose me vendim njerëzor
Klikimi zgjedh raportin dhe shfaq panelin anësor me:
Përmbledhje hetimi
Overall risk score
Rekomandim AI
Eksport: JSON (download file) ose PDF (window.print)
Buton "Export All (JSON)" për të gjitha raportet
Link te Analytics
5.7 Settings (/settings)
Konfigurime të ndara në seksione:

Account: avatar me iniciale, emër, email, ndryshim fjalëkalimi (UI only, nuk ruan)
Appearance: light / dark / system theme
Notifications: toggle për high-risk alerts, investigation completed, human review required
Investigation Preferences: auto-assign, require decision notes, high-risk threshold slider (50–95)
AI Configuration: model (Amazon Nova Pro), human-in-the-loop, agent weights (50/50), PII removal
Lista e agjentëve aktivë (3 MVP)
Lista e agjentëve roadmap (3 të ardhshëm)
Security & Privacy: PII protection, audit logging, human oversight
Shumica e settings janë UI-only — nuk ruhen në storage.

6. Sistemi i Agjentëve AI
Agjentët aktivë (MVP)
Visual Evidence Agent — analizon imazhet e ngarkuara për manipulim dhe autenticitet (metadata EXIF, software editimi, pattern dëmtimi)
Claim Intelligence Agent — analizon shpjegimin e klientit për sinjale mashtrimi (gjuha urgjente, mospërputhje timeline, ngjashmëri me pattern të njohura)
Orchestrator Agent — kombinon output-et e agjentëve me pesha të barabarta (50/50) për risk score final dhe rekomandim
Agjentët në roadmap (jo implementuar)
Shipment Verification Agent — verifikim tracking carrier
Marketplace Intelligence Agent — cross-reference historiku marketplace
Threat Intelligence Agent — përputhje me pattern syndikatash mashtrimi
Logjika e analizës (simulim)
Kur krijohet hetim i ri, analysisApi.runAnalysis():

Ekzekuton 3 faza me delay 1.4s secilën
Gjeneron score të rastësishëm bazuar në input:
Me imazh: visual score 55–85, claim score 40–75, risk = mesatarja 50/50
Pa imazh: vetëm claim score, visual = 0
Rekomandimi: < 35 = Approve, 35–74 = Manual Review, ≥ 75 = Escalate
Modeli i referuar në UI: Amazon Nova Pro v1.0 (simulim, jo integrim real).

Nivelet e riskut
0 = Insufficient Data (pa imazh)
1–39 = Low Risk (jeshile)
40–69 = Elevated (verdhë/amber)
70–100 = High Risk (kuqe)
7. Të Dhënat Sintetike (Seed Data)
5 hetime fillestare
Claim ID	Produkti	Kategoria	Risk	Status	Rekomandim AI	Vendim njerëzor
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
— (pa imazh)
CLM-005
Smart Watch Series 9
Electronics
61 (Elevated)
Resolved
Manual Review
Rejected
Çdo hetim ka: shpjegim klienti, score/confidence për çdo agjent, findings, metadata imazhi, audit trail, përmbledhje, notes.

Të dhëna analitike
KPI, grafikë aktiviteti, shpërndarje risku/rekomandimi/vendimi, performancë agjentësh — të gjitha statike në src/data/analytics.ts.

Store në memorie
investigationsApi mban një array në memorie (let store). Hetimet e reja shtohen në fillim. Vendimet njerëzore përditësohen në store. Të dhënat reset-ohen me refresh të faqes.