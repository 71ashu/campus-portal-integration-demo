# Campus Portal Integration Demo

A demo that takes the [AI Course Advisor](https://github.com/71ashu/AI-Course-Advisor)
recommendation engine out of standalone mode and shows how it deploys into a real
university: reading a student's academic record from the school's SIS and degree-audit
system as it updates, instead of owning its own seed data, and living inside a
university-portal shell instead of being its own island.

Design rationale, architecture decisions, and the interview talking points this is
meant to unlock: [`docs/portal-integration-demo.md`](docs/portal-integration-demo.md).

**🔗 Live demo:** _TODO — add the deployed URL here after following [`DEPLOY.md`](DEPLOY.md)._
Runs on Render's + Vercel's free tiers, so the first load may take ~30–60s to wake up.

> **Not affiliated with Santa Clara University.** The catalog, program rules, and
> university branding in this demo reference Santa Clara University's real MS in
> Computer Science and Engineering (course numbers, titles, and the 6-unit EMGT
> elective cap are sourced from its public Graduate Engineering Bulletin) to make
> the "adapts to a real institution" claim concrete — this is an unofficial personal
> project, not built, endorsed, or operated by SCU.

## What's here

```
mock-sis/            Stands in for the university's SIS + degree audit
                      (Banner/PeopleSoft/Workday Student + DegreeWorks/Stellic).
                      In-memory Flask service + a Registrar console.

advisor-backend/      The recommendation engine. services.py, knowledge_graph.py,
                      collaborative.py, and grade_predictor.py are byte-for-byte
                      what the standalone project has — nothing about the engine
                      changed. integrations/sis_client.py is the ONLY new code
                      that talks to the SIS; it's the entire integration surface.

advisor-frontend/     The existing AI Course Advisor UI, now wrapped in a
                      university-portal shell (top bar + nav) with a mock SSO
                      login and a "Synced from SIS" provenance strip.
```

## The story in one sentence

**The engine doesn't change — only the data source does.** `seed.py`'s hardcoded
courses/students become `mock-sis`'s fixtures; the same `services.py` scoring engine
now scores courses pulled from there instead.

## Architecture

```
 Portal (advisor-frontend)              Mock SIS (mock-sis)
 ┌─────────────────────────┐            ┌───────────────────────────┐
 │ SCU-styled top bar + nav │            │ course catalog + prereqs   │
 │  └ Course Planning       │            │ degree program + audit     │
 │     (the advisor app,    │            │ student academic history   │
 │      unmodified)         │            │                            │
 │                          │            │ Registrar console:         │
 │ mock SSO: University ID  │            │  POST a final grade  ──┐   │
 │ "Synced from SIS" badge  │            │                        │   │
 └───────────┬──────────────┘            └────────────────────────┼───┘
             │ session cookie                                     │ webhook
             ▼                                                    ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ Advisor backend (advisor-backend)                                │
 │                                                                   │
 │  services.py / knowledge_graph.py / collaborative.py /           │
 │  grade_predictor.py  ← UNCHANGED, only ever read local DB rows   │
 │                                                                   │
 │  integrations/sis_client.py  ← the entire integration surface:   │
 │    sync_catalog_and_program()   upserts Course / Program rows    │
 │    sync_student()               upserts Student / StudentCourse  │
 │                                                                   │
 │  POST /api/auth/sso                 mock campus SSO              │
 │  POST /api/sync                     manual "Refresh from SIS"    │
 │  POST /api/webhooks/sis/grade-posted   pushed by the SIS          │
 └───────────────────────────────────────────────────────────────────┘
```

## Setup

Requires Python 3.10–3.12 (not 3.13 — some dependencies don't have wheels for it yet)
and Node 18+. Three processes, three terminals:

### 1. Mock SIS

```bash
cd mock-sis
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py            # http://localhost:5050
```

Visit `http://localhost:5050` for the Registrar console.

### 2. Advisor backend

```bash
cd advisor-backend
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
./venv/bin/python app.py            # http://localhost:5000
```

On first start it pulls the catalog + program from the mock SIS (must already be
running) and seeds ~18 synthetic background students so collaborative filtering and
grade prediction have data to work with — mirroring what the standalone project's
`seed.py` did, except the courses come from the SIS instead of a hardcoded list.

### 3. Advisor frontend (the portal)

```bash
cd advisor-frontend
npm install
npm run dev                         # http://localhost:5173
```

Visit **http://localhost:5173** and sign in as one of the two seeded students —
no password, just a campus ID (that's the SSO story).

## Demo script (~2 minutes)

Catalog is Santa Clara University's real MS in Computer Science and Engineering
(MS-CSEN): three graduate core courses (Computer Architecture, Algorithms, Operating
Systems), a math/ML elective track, and real EMGT/ENGR electives — including the
program's actual "max 6 units of EMGT electives" rule.

1. **Sign in.** At `http://localhost:5173`, click **Jordan Rivera · M00412771** on the
   portal login screen. Land on the Dashboard: GPA, credits, current courses, and
   program requirements — all labeled **"Synced from SIS · just now"**, not typed in
   anywhere.
2. **Ask for recommendations.** Go to *Ask Advisor* → "What machine learning courses
   should I take next?" *Machine Learning (CSEN 240)* shows up but locked — Jordan
   has finished Probability I (AMTH 210) and Algorithms (CSEN 279), but is only
   mid-way through *Linear Algebra II (AMTH 246)*, which CSEN 240 also requires.
3. **Play registrar.** Open `http://localhost:5050/registrar/M00412771` in another tab.
   Post a final grade: **A- in AMTH 246**, then **D+ in Operating Systems (CSEN 283)**.
   Each post shows "Advisor synced ✅" — that's the webhook firing.
4. **Watch it update.** Back on the portal tab, click **Refresh from SIS** (or wait
   ~8s for the background poll). The assistant posts a new message: *Machine Learning
   (CSEN 240)* is now eligible — *All prerequisites completed* — and jumps to the top;
   the GPA on the Dashboard drops from 3.57 to 3.13; predicted-grade numbers on the
   other recommendations shift down with it.
5. **The punchline.** Nothing in `services.py` or `knowledge_graph.py` ran differently
   before and after step 4. The only thing that changed was the student's record in
   the SIS.

## What's deliberately out of scope

Named here rather than silently skipped — see
[`docs/portal-integration-demo.md`](docs/portal-integration-demo.md) for the reasoning:

- **Real LTI 1.3 / SAML / OIDC** — the portal's "Sign in with University ID" is a
  stand-in for a real SSO/LTI launch, not an implementation of one.
- **True push (SSE/websockets)** — the frontend short-polls `/api/progress` every 8s
  and diffs `sisSyncedAt`; a real deployment would push over the webhook instead of
  polling for it. The webhook itself (SIS → advisor) is real.
- **Multi-tenant / multiple institutions** — one program, one catalog, two students.
- **FERPA / data-handling review** — this is a demo with synthetic data; a real
  integration would need one.
- **Onboarding cold-start** — skipped entirely for portal students, since anyone
  arriving via SSO already has a full SIS academic record to sync instead of an empty
  profile to bootstrap.
