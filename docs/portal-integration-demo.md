# Portal Integration Demo — Design Spec

**Purpose:** Turn AI Course Advisor from a standalone app into a *recommendation layer
that plugs into a university's existing systems of record*, and build a demo that shows
the integration seam working end to end. This is the artifact that makes the project
credible for Forward Deployed Engineer (FDE) interviews.

**Status:** Built. This repo *is* the demo described below — `mock-sis/`,
`advisor-backend/`, `advisor-frontend/` implement sections 2–5. A few choices were
resolved pragmatically during the build rather than left as open questions:
SQLite (not Postgres) for the advisor's own database, an in-memory fixture-backed
store (not a real DB) for the mock SIS, short polling + a real webhook instead of
SSE for the "live" update (see the top-level README's "deliberately out of scope"
section), and the demo's course codes (CS331/CS356/MATH231) replaced the
illustrative ones this doc originally sketched. See the top-level
[`README.md`](../README.md) for setup and the actual demo script.

---

## 1. The argument this demo has to make

Today the advisor owns all its data: `seed.py` invents courses, programs, 30 synthetic
students, their enrollments and grades. In a real deployment the university *already
has* this data and keeps it current:

| Data the advisor needs        | Where a university already keeps it, maintained live |
|-------------------------------|------------------------------------------------------|
| Course catalog + prerequisites | SIS course catalog (Banner, PeopleSoft, Workday Student) |
| Degree program requirements    | Degree audit system (DegreeWorks, Stellic, u.achieve) |
| Student's completed courses, grades, GPA | SIS academic history / transcript |
| Current-term enrollment        | SIS registration |
| Real-time progress changes     | Grades post at end of term → student state changes |

So the product is not "a recommender." It is **an explainable recommendation layer that
reads student progress from the SIS/degree-audit as it updates, and surfaces
next-course suggestions inside the portal the student already logs into.**

The demo has to show three things:

1. **The engine reads from an external system of record**, not its own seed data.
2. **Recommendations recompute when the student's record changes** (a grade posts).
3. **The UI lives inside a portal**, not on its own island (branded shell + SSO handoff).

The punchline for every version of the demo: *the scoring engine
(`services.py`, `knowledge_graph.py`) does not change — only the data source does.*
The codebase already hints at this with `seed_engr_emgt.py` adapting the engine to a
real program's catalog.

---

## 2. Target architecture

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│   "MSU" Portal shell     │        │        Mock SIS service       │
│   (frontend/portal/)     │        │        (mock-sis/)            │
│                          │        │                              │
│  top bar + left nav      │        │  system of record:           │
│  ├ Home                   │        │   - course catalog + prereqs │
│  ├ Registration           │        │   - degree programs + rules  │
│  ├ Financial Aid          │        │   - student academic history │
│  └ Course Planning ───────┼──┐     │   - term enrollments + grades│
│      embeds the advisor   │  │     │                              │
│                          │  │     │  REST:                       │
│  mock SSO: "Sign in with  │  │     │   GET  /sis/catalog          │
│   University ID"          │  │     │   GET  /sis/programs/:id      │
└─────────────────────────┘  │     │   GET  /sis/students/:id      │
             │                │     │   GET  /sis/students/:id/progress
             │ embed (iframe   │     │   POST /sis/students/:id/grades  ← registrar action
             │  or same SPA)   │     │   (webhook out on grade post)│
             ▼                │     └───────────────┬──────────────┘
┌─────────────────────────┐  │                     │
│   Advisor backend        │◄─┘                     │ pull on sync / webhook in
│   (backend/)             │                        │
│                          │  backend/integrations/sis_client.py
│  services.py   ──────────┼──  unchanged           │
│  knowledge_graph.py ─────┼──  unchanged           ▼
│  collaborative.py ───────┼──  unchanged     maps SIS payloads → Course / Program /
│  grade_predictor.py ─────┼──  unchanged     Student / StudentCourse rows
│                          │
│  NEW: POST /api/sync/:studentId   (re-pull this student from SIS, recompute)
│  NEW: SIS provenance fields on progress/recommend responses
└─────────────────────────┘
```

### Why a separate mock SIS instead of just more seed data

The whole point is the *seam*. If the data still comes from inside `backend/`, there is
no integration story. A separate service with its own REST contract forces the adapter
to exist and makes "swap the data source" literally true on screen. It also lets the
demo show a **registrar posting a grade in a different system** and the advisor reacting.

Keep it small: one Flask (or FastAPI) file, SQLite or in-memory, seeded from a JSON
fixture that looks like a real catalog export. It does not need auth beyond a shared
token.

---

## 3. Integration contract (mock SIS → advisor)

The adapter `sis_client.py` is the only new code that touches the advisor's domain
model. It maps SIS shapes to existing tables in `models.py`.

### `GET /sis/students/:id/progress` (the important one)

```jsonc
{
  "student": {
    "sisId": "M00412771",
    "name": "Jordan Rivera",
    "programId": "BS-CS-2024",
    "catalogYear": "2024-2025",
    "classStanding": "Junior",
    "cumulativeGpa": 3.42
  },
  "courseHistory": [
    { "courseCode": "CS 201", "term": "2025SP", "status": "completed",
      "grade": "A-", "gradePoints": 3.7, "units": 4 },
    { "courseCode": "MATH 231", "term": "2025SP", "status": "completed",
      "grade": "B",  "gradePoints": 3.0, "units": 3 },
    { "courseCode": "CS 301", "term": "2025FA", "status": "in_progress",
      "units": 4 }
  ],
  "degreeAudit": {
    "programId": "BS-CS-2024",
    "totalUnitsRequired": 120,
    "unitsCompleted": 58,
    "minimumGpa": 2.0,
    "unmetRequirements": [
      { "block": "CS Core", "needs": ["CS 301", "CS 331", "CS 356"] },
      { "block": "CS Electives", "needsUnits": 12 },
      { "block": "Math/Science", "needsUnits": 3 }
    ]
  },
  "asOf": "2026-09-08T22:14:03Z"
}
```

### Mapping performed by `sis_client.py`

| SIS field | Advisor table.column | Notes |
|-----------|----------------------|-------|
| `student.sisId` | `Student.email` (synthetic: `M00412771@msu.edu`) or a new `sis_id` column | one small migration |
| `student.programId` | `Student.program_enrolled` | resolve against `Program` |
| `student.cumulativeGpa` | `Student.program_gpa` | drives the GPA-protection penalty in `services.py` |
| `courseHistory[].status=completed` | `StudentCourse(status='completed')` + `grade_points`, `course_gpa` | feeds `knowledge_graph.get_reachable_courses` |
| `courseHistory[].status=in_progress` | `StudentCourse(status='current')` | |
| `degreeAudit.unmetRequirements` | scope candidate courses in `get_recommendations` | replaces the `ProgramCourse` scoping heuristic with the *actual* audit |
| `GET /sis/catalog` `prerequisites` | `Course.prerequisites` | feeds the NetworkX DAG build |
| `asOf` | new provenance field on API responses | UI shows "Synced from SIS · 2 min ago" |

**Design note for the interview:** the degree audit's `unmetRequirements` is strictly
better input than what the app does today (`_resolve_program_for_student` + fuzzy
name matching + `ProgramCourse` junction). Real integration *simplifies* the engine
because the customer's system already answers "what's left."

### Sync triggers

- **On demand:** `POST /api/sync/:studentId` — re-pull, remap, recompute. Wired to a
  "Refresh from SIS" button for the demo.
- **Push:** mock SIS fires a webhook `POST /api/webhooks/sis/grade-posted` after a
  registrar posts grades; advisor re-syncs that student and (demo) pushes a
  server-sent event so the open portal tab refreshes its recommendations live.

---

## 4. Portal shell

`frontend/portal/` — a thin wrapper, not a rebuild.

- **Branded chrome:** university name + crest in a top bar, maroon/gold theme,
  left nav: Home / Registration / Financial Aid / Advising / **Course Planning**.
  Only "Course Planning" is real; the rest are static stubs that sell the context.
- **Mock SSO:** a "Sign in with University ID" button → posts the SIS id to a new
  `POST /api/auth/sso` that trusts a shared secret (demo only), creates/loads the
  `Student`, triggers an initial SIS sync, sets the session. No password screen —
  that *is* the SSO story.
- **Embed:** simplest is to render the existing `CourseAdvisor.jsx` inside the portal
  layout as a route. An `<iframe>` is more honest to "separately deployed app embedded
  via LTI" but adds session/CORS friction; decide at build time. Note in the demo
  script which one was used and why.
- **Provenance UI:** a small "Data synced from Midwestern State SIS · 2 min ago ·
  Refresh" strip above the recommendations, and on the progress panel label completed
  courses as "from academic history."

**Not doing for the demo (but name them as the real path):** true LTI 1.3 launch,
SAML/OIDC SSO, Ed-Fi / OneRoster rostering feeds, FERPA data handling review.

---

## 5. Demo script (~2 min)

1. **Portal login.** Land on the MSU portal. Click "Sign in with University ID."
   Land on the portal home, click **Course Planning**.
2. **First recommendations.** Advisor shows 6 courses. Point at the provenance strip:
   "synced from the SIS." Point at the progress panel: "58 of 120 units, 3.42 GPA —
   that's the degree audit, not something we typed in." Each recommendation still
   has its explainability pills (prereq / interest / peer pattern / GPA prediction).
3. **A grade posts.** Switch to the **Registrar** view (a page on the mock SIS).
   Post Fall grades for Jordan: `A` in CS 301, `D+` in MATH 231 retake.
4. **Live reaction.** Back on the portal tab (no reload): the provenance strip flips
   to "synced just now." Recommendations change:
   - CS 331 and CS 356 move up — CS 301 is now a completed prerequisite (NetworkX
     `get_reachable_courses` picks it up).
   - A math-heavy elective drops / gets a GPA-warning pill — the D+ pulled the
     predicted grade below the threshold in `services.py`.
   - Units completed ticks up; "CS Core" block shrinks in the audit.
5. **Punchline.** "The recommendation engine didn't change at all between these two
   screens. The only thing that changed is the student's record in the SIS. This is
   how it deploys into a university that already runs DegreeWorks and Banner."

---

## 6. Build plan (when we're ready)

Ordered so each step is demoable on its own.

| # | Step | Files | Rough size |
|---|------|-------|-----------|
| 1 | Mock SIS service with JSON-fixture catalog, programs, 3–4 students | `mock-sis/app.py`, `mock-sis/fixtures/*.json` | 0.5 day |
| 2 | `sis_client.py` adapter + `POST /api/sync/:studentId`; point one demo student at the SIS instead of `seed.py` | `backend/integrations/sis_client.py`, `backend/app.py`, one migration for `sis_id` | 0.5 day |
| 3 | Provenance fields on `/api/progress` + `/api/recommend`; "Refresh from SIS" button | `backend/services.py`, `backend/app.py`, `frontend/src/components/course-advisor/*` | 0.25 day |
| 4 | Registrar page on mock SIS (`POST /sis/students/:id/grades`) + webhook out | `mock-sis/app.py` | 0.25 day |
| 5 | Webhook in + SSE push so the portal tab live-updates | `backend/app.py`, `frontend` SSE hook | 0.5 day |
| 6 | Portal shell + mock SSO (`POST /api/auth/sso`) | `frontend/portal/`, `backend/app.py` | 0.75 day |
| 7 | Demo polish: theming, seed a believable student, script rehearsal, README + Loom | docs, README | 0.5 day |

**~3.5 days.** Steps 1–3 alone (≈1.25 days) already deliver the core FDE talking
point ("engine reads from an external system of record"); 4–7 add the live/embedded
story.

### Dependencies / decisions to make at build time
- Mock SIS framework: reuse Flask (consistency) vs. FastAPI (nicer for a throwaway).
- Embed as SPA route vs. iframe (session + CORS trade-off).
- SSE vs. short polling for the live update (SSE is more impressive, polling is 10 min
  of work).
- Add `Student.sis_id` column vs. overload `email`. A real column is cleaner and is
  itself a talking point about integration keys.

---

## 7. Interview talking points this unlocks

- **"Standalone vs. deployed."** "The v1 was standalone with synthetic data. I
  refactored it so the engine reads a student's progress from the university's SIS
  and degree-audit system — the data they already maintain — and I built a mock SIS
  with a real integration contract to prove the seam."
- **"Integration simplifies the product."** The degree audit already answers "what
  requirements are unmet," so the fuzzy program-matching heuristic in `services.py`
  gets *deleted*, not extended. FDE work is often about leaning on the customer's
  existing sources instead of rebuilding them.
- **"Real-time."** "When a grade posts in the SIS, a webhook re-syncs that student and
  the open advising session updates live — newly satisfied prerequisites unlock
  courses, a low grade triggers a GPA-protection warning."
- **"Why not just use DegreeWorks?"** Degree audits tell a student *what's left*, not
  *what to take next* given interests, peer enrollment patterns, and GPA risk — and
  they don't explain the reasoning. That gap is the multi-signal + explainability
  layer.
- **"Deployment realities I scoped out but know about."** LTI 1.3 launch, OIDC/SAML
  SSO, Ed-Fi/OneRoster feeds, FERPA review, per-institution catalog quirks
  (cross-listed courses — already handled via `alt_codes`).

---

## 8. Open questions

- Which real degree-audit vendor to model the contract on (DegreeWorks is the most
  common; its "Scribe" requirement language is a rabbit hole — model the *output*,
  not Scribe).
- Do we want a second institution fixture to show multi-tenant / "same engine,
  different school" in the same demo?
- Is a hosted deployment (Fly + Vercel) in scope alongside this, or a separate task?
