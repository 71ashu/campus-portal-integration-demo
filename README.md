# Campus Portal Integration Demo

The "university side" of an integration with the
[AI Course Advisor](https://github.com/71ashu/AI-Course-Advisor): a campus student
portal that launches the advisor inside an iframe the way Canvas or Blackboard
launches an LTI tool, and a mock SIS / degree-audit service that is the system of
record for every student's courses and grades.

None of the advisor's code lives here. The advisor is a separately deployed product;
this repo is the customer it plugs into.

Design rationale and interview talking points:
[`docs/portal-integration-demo.md`](docs/portal-integration-demo.md).

**🔗 Live demo:** https://campus-portal-integration-demo.vercel.app — still runs the
earlier version of this demo (advisor copied into this repo, cookie SSO). It has not
been redeployed with the iframe launch yet; see [`DEPLOY.md`](DEPLOY.md).

> **Not affiliated with Santa Clara University.** The catalog, program rules, and
> university branding in this demo reference Santa Clara University's real MS in
> Computer Science and Engineering (course numbers, titles, and the 6-unit EMGT
> elective cap are sourced from its public Graduate Engineering Bulletin) to make
> the "adapts to a real institution" claim concrete — this is an unofficial personal
> project, not built, endorsed, or operated by SCU.

## What's here

```
portal-server/   The campus portal (the LTI "platform"). Owns student sign-in,
                 signs launch tokens with its RSA key, publishes its public key at
                 /.well-known/jwks.json, and frames the advisor on Course Planning.

mock-sis/        Stands in for the SIS + degree audit (Banner/PeopleSoft/Workday
                 Student + DegreeWorks/Stellic). In-memory Flask service, API-key
                 protected, with a Registrar console that posts grades and sends
                 HMAC-signed webhooks.
```

The advisor itself runs from the AI-Course-Advisor repo, configured for this campus
(its own database, this portal registered as a platform, this SIS as a data source).

## How the pieces talk

```
 Browser                                                    
 ┌───────────────────────────────────────────────┐          
 │ Portal 127.0.0.1:5100  (portal-server)        │          
 │  ┌─────────────────────────────────────────┐  │          
 │  │ <iframe> Advisor app  localhost:5173    │  │  postMessage: ready / synced /
 │  │   Authorization: Bearer <embed token>   │◄─┼─ session-expired / logout
 │  └──────────────────┬──────────────────────┘  │          
 └─────────────────────┼─────────────────────────┘          
   1 signed launch     │ 3 API calls                         
   (RS256 JWT, 60s)    ▼                                     
 ┌─────────────────────────────────┐   4 GET /sis/... (API key)   ┌──────────────┐
 │ Advisor API  localhost:5000     ├─────────────────────────────►│ mock SIS     │
 │  2 verifies JWT via portal JWKS │◄─────────────────────────────┤ :5050        │
 │    → one-time code → session    │   5 grade.posted webhook     │ + Registrar  │
 └─────────────────────────────────┘     (HMAC-SHA256 signed)     └──────────────┘
```

1. **Launch.** The Course Planning iframe loads the portal's `/launch/advisor`, which
   auto-POSTs a 60-second RS256 launch token (LTI 1.3 claim shape) to the advisor.
2. **Verify.** The advisor checks the signature against the portal's JWKS plus
   issuer, audience, deployment, expiry and replay, then redirects the iframe to its
   app with a single-use code in the URL fragment.
3. **Session.** The app trades the code for a bearer token. Cookies would be
   third-party inside the iframe, so the token goes in an `Authorization` header.
4. **Data.** Grades and course history never pass through the portal. The advisor
   pulls them from the SIS with its own API key.
5. **Updates.** When the registrar posts a grade, the SIS sends a signed webhook that
   names only the student. The advisor re-pulls the record, and the open iframe
   notices within 8 seconds.

Different hostnames (`127.0.0.1` vs `localhost`) are deliberate: browsers ignore
ports when deciding what's "same-site", so this is what makes local development
behave like a real cross-site embed.

## Setup

Requires Python 3.10–3.12, Node 18+, PostgreSQL, and a checkout of
[AI-Course-Advisor](https://github.com/71ashu/AI-Course-Advisor) next to this repo.

### 1. Mock SIS (:5050)

```bash
cd mock-sis
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env     # then set SIS_API_KEYS and SIS_WEBHOOK_SECRET (step 3)
./venv/bin/python app.py
```

### 2. Portal (:5100)

```bash
cd portal-server
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
./venv/bin/python app.py     # generates keys/portal_private.pem on first start
```

### 3. Advisor, deployed for this campus (:5000 API, :5173 app)

In the AI-Course-Advisor repo, create `backend/.env.scu` (gitignored) with its own
database and the SIS credentials, and put the same two secrets in `mock-sis/.env`:

```bash
# backend/.env.scu
FLASK_ENV=development
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/course_advisor_scu
SECRET_KEY=...
OPENAI_API_KEY=...            # optional
FRONTEND_URL=http://localhost:5173
SCU_SIS_API_KEY=...           # same value in mock-sis SIS_API_KEYS
SCU_SIS_WEBHOOK_SECRET=...    # same value in mock-sis SIS_WEBHOOK_SECRET
```

Then create the schema, register this portal, and pull the catalog (the SIS must be
running):

```bash
cd backend
createdb course_advisor_scu
export ENV_FILE=.env.scu FLASK_APP=app
./venv/bin/python -c "from app import app, db; app.app_context().push(); db.create_all()"
./venv/bin/flask db stamp head
./venv/bin/flask embed register-platform --key scu --name "Santa Clara University" \
  --issuer http://127.0.0.1:5100 --client-id scu-portal --deployment-id scu-1 \
  --jwks-url http://127.0.0.1:5100/.well-known/jwks.json \
  --portal-origin http://127.0.0.1:5100 \
  --sis-base-url http://localhost:5050 --sis-program-id MS-CSEN \
  --sis-api-key-env SCU_SIS_API_KEY --webhook-secret-env SCU_SIS_WEBHOOK_SECRET
./venv/bin/flask embed sync-catalog --platform scu
```

Run it (two terminals, from the AI-Course-Advisor repo):

```bash
cd backend && ENV_FILE=.env.scu ./venv/bin/python app.py
```

```bash
cd frontend && npm run dev
```

Open **http://127.0.0.1:5100** (not `localhost`) and sign in as one of the seeded
students.

## Demo script (~2 minutes)

Catalog is Santa Clara University's real MS in Computer Science and Engineering
(MS-CSEN): three graduate core courses (Computer Architecture, Algorithms, Operating
Systems), a math/ML elective track, and real EMGT/ENGR electives — including the
program's actual "max 6 units of EMGT electives" rule.

1. **Sign in to the portal.** At `http://127.0.0.1:5100`, click **Jordan Rivera ·
   M00412771**. Course Planning opens with the advisor inside it. The student signed
   in to the portal only; the advisor received a signed launch, not a password.
2. **Ask for recommendations.** Go to *Ask Advisor* → "What machine learning courses
   should I take next?" *Machine Learning (CSEN 240)* shows up but locked — Jordan
   has finished Probability I (AMTH 210) and Algorithms (CSEN 279), but is only
   mid-way through *Linear Algebra II (AMTH 246)*, which CSEN 240 also requires.
3. **Play registrar.** Open `http://localhost:5050/registrar/M00412771` in another tab.
   Post **A- in AMTH 246**, then **D+ in Operating Systems (CSEN 283)**. Each shows
   "Advisor synced ✅" — the signed webhook was accepted.
4. **Watch it update.** Back on the portal, within ~8s the assistant posts a new
   message: *Machine Learning (CSEN 240)* is now eligible and jumps to the top; the
   GPA drops from 3.57 to 3.13; predicted grades shift down with it. The portal's
   header shows when the advisor last synced, reported by the iframe over
   `postMessage`.
5. **The punchline.** The portal and the advisor are separate deployments. Nothing in
   the advisor's engine changed; the only thing that changed was the student's record
   in the SIS.

Use the Registrar's **Reset demo data** button (or restart `mock-sis`) between runs.

## What's deliberately out of scope

- **Full LTI 1.3.** The launch uses LTI 1.3's message and claim shapes, RS256 and
  JWKS, but skips the OIDC login-initiation redirect and LTI Advantage services.
  Adding that redirect is the step to launching from a real Canvas.
- **Real SSO.** The portal's "Sign in with University ID" stands in for
  Shibboleth/Okta/Entra; there is no password.
- **OAuth2 for the SIS API.** The advisor authenticates with a static API key; a real
  SIS would issue scoped client-credential tokens.
- **True push to the browser.** The iframe polls `/api/progress` every 8s; the
  server-to-server webhook is real.
- **FERPA / data-handling review.** Synthetic data only; a real integration needs one.
