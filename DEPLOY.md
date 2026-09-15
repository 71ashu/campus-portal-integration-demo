# Deploying the live demo

Three services, deployed in this order because two of them need each other's URL:

1. **mock-sis** → Render web service
2. **advisor-backend** → Render web service (needs mock-sis's URL)
3. **advisor-frontend** → Vercel (needs advisor-backend's URL)

Then you go back and fill in mock-sis's webhook URL once advisor-backend exists.
Takes about 10–15 minutes end to end. Free tiers throughout.

## 1. Push this repo to GitHub

Already done if you're reading this from the repo. Render and Vercel both deploy
by connecting to a GitHub repo.

## 2. Deploy both Flask services on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect this GitHub repo. Render reads [`render.yaml`](render.yaml) at the root
   and proposes two services: `campus-mock-sis` and `campus-advisor-backend`.
3. Click **Apply**. Both will fail to fully work on the first deploy — that's
   expected, they don't have each other's URLs yet.
4. Once both have deployed, copy each service's URL from the Render dashboard
   (`https://campus-mock-sis-XXXX.onrender.com` and
   `https://campus-advisor-backend-XXXX.onrender.com`).
5. On **campus-advisor-backend** → Environment, set:
   - `SIS_BASE_URL` = the campus-mock-sis URL from step 4 (no trailing slash)
   - `FRONTEND_URL` = leave as-is for now, you'll come back after step 3 below
6. On **campus-mock-sis** → Environment, set:
   - `ADVISOR_WEBHOOK_URL` = `<campus-advisor-backend URL>/api/webhooks/sis/grade-posted`
7. Manually trigger a redeploy on both (Render does this automatically on env
   var changes, but confirm both show "Live" before moving on).
8. Sanity check: `curl https://<campus-mock-sis URL>/sis/health` and
   `curl https://<campus-advisor-backend URL>/api/health` should both return
   `{"status": "ok"}` / `{"status": "healthy", ...}`.

**Free-tier note:** Render's free web services spin down after 15 minutes of
inactivity and take 30–60 seconds to wake up on the next request. The first
load of a shared demo link may look like it's hanging — it isn't. This also
affects the registrar's grade-posted webhook: if `campus-advisor-backend` is
asleep, posting a grade in the Registrar console can take up to ~60s to show
"Advisor synced ✅" while it wakes up. Visiting the portal URL once first
(to wake the backend) before doing a registrar demo avoids the wait.

## 3. Deploy the frontend on Vercel

```bash
vercel login          # interactive — only you can do this step
cd advisor-frontend
vercel link            # first time: create a new project, don't link to an existing one
vercel env add VITE_API_BASE production
# paste: https://<campus-advisor-backend URL>/api
vercel --prod
```

Or via the Vercel dashboard: **New Project** → import this repo → set
**Root Directory** to `advisor-frontend` → add the `VITE_API_BASE` environment
variable → Deploy.

## 4. Close the loop

Copy the Vercel URL Vercel gives you, then:

- Back on Render, set **campus-advisor-backend**'s `FRONTEND_URL` to that Vercel
  URL (needed for CORS) and let it redeploy.

## 5. Verify the live demo

Open the Vercel URL, sign in as Jordan Rivera, ask the advisor a question, then
open `<campus-mock-sis URL>/registrar/M00412771` in another tab and post a grade.
The portal tab should update within ~8 seconds (or immediately via "Refresh from
SIS"). This is the same flow as the [README's demo script](README.md#demo-script-2-minutes),
just on public URLs instead of localhost.

If the registrar page ever gets left in a confusing state after other people
have poked at the public demo, its "Reset demo data" button restores the
seeded starting state.

## Notes / limitations of this deployment

- **Data doesn't persist across Render redeploys.** SQLite lives on the
  service's ephemeral disk; mock-sis is in-memory. A redeploy resets both to
  their seeded starting state — for a demo, that's a feature, not a bug.
- **No auth on the Registrar console.** It's part of the point — a real SIS
  wouldn't be open to the internet like this — but don't put anything in the
  fixtures you wouldn't want a stranger to see or edit.
- **Optional `SIS_WEBHOOK_TOKEN`:** set the same non-empty value on both
  services' env vars to require it on the grade-posted webhook. Left blank by
  default so the first deploy works without extra setup.
