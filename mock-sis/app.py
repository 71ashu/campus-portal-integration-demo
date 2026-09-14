"""
Mock SIS (Student Information System) + Degree Audit service.

Stands in for a real university system of record (Banner / PeopleSoft /
Workday Student for course history + registration, DegreeWorks / Stellic for
the degree audit). Everything here is deliberately small and in-memory: the
point of this service is the *contract* — the shapes the advisor's
integrations/sis_client.py adapts into its own domain model — not a real SIS
implementation.

Also serves a tiny server-rendered "Registrar" console so the demo can post a
grade for a student without touching the advisor or the portal at all, the
way a real registrar would in Banner. Posting a grade fires a best-effort
webhook back to the advisor so its data stays in sync without a manual
"Refresh" click.
"""
import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, request, url_for

load_dotenv()

FIXTURES_DIR = Path(__file__).parent / "fixtures"

ADVISOR_WEBHOOK_URL = os.getenv(
    "ADVISOR_WEBHOOK_URL", "http://localhost:5000/api/webhooks/sis/grade-posted"
)
SIS_WEBHOOK_TOKEN = os.getenv("SIS_WEBHOOK_TOKEN", "")

app = Flask(__name__)

_lock = threading.Lock()


def _load_json(name):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _reset_state():
    """(Re)load the in-memory store from the fixture files. Everything here
    resets on process restart on purpose — this is a demo fixture, not a
    real database."""
    global CATALOG, PROGRAMS, STUDENTS
    CATALOG = {c["id"]: c for c in _load_json("catalog.json")}
    PROGRAMS = {p["id"]: p for p in _load_json("programs.json")}
    STUDENTS = {s["sisId"]: deepcopy(s) for s in _load_json("students.json")}


_reset_state()


# --------------------------------------------------------------------------
# Degree audit computation (stands in for DegreeWorks/Stellic)
# --------------------------------------------------------------------------

def _course(course_code):
    return CATALOG.get(course_code)


def _completed_codes(student):
    return {
        c["courseCode"] for c in student["courseHistory"] if c["status"] == "completed"
    }


def _units_for(codes):
    return sum((_course(c) or {}).get("units", 0) for c in codes)


def _cumulative_gpa(student):
    total_units = 0
    total_points = 0.0
    for entry in student["courseHistory"]:
        if entry["status"] != "completed" or entry.get("gradePoints") is None:
            continue
        course = _course(entry["courseCode"])
        if not course:
            continue
        units = course.get("units", 0)
        total_units += units
        total_points += entry["gradePoints"] * units
    if total_units == 0:
        return 0.0
    return round(total_points / total_units, 3)


def _degree_audit(student):
    program = PROGRAMS.get(student["programId"], {})
    completed = _completed_codes(student)

    core_ids = program.get("coreCourseIds", [])
    elective_ids = set(program.get("electiveCourseIds", []))
    min_elective_units = program.get("minElectiveUnits", 0)

    missing_core = [cid for cid in core_ids if cid not in completed]
    elective_units_done = _units_for(completed & elective_ids)
    elective_units_needed = max(min_elective_units - elective_units_done, 0)

    unmet = []
    if missing_core:
        unmet.append({
            "block": "Core Requirements",
            "needs": missing_core,
        })
    if elective_units_needed > 0:
        unmet.append({
            "block": "Electives",
            "needsUnits": elective_units_needed,
        })

    return {
        "programId": student["programId"],
        "totalUnitsRequired": program.get("totalUnitsRequired"),
        "unitsCompleted": _units_for(completed),
        "minimumGpa": program.get("minimumGpa"),
        "unmetRequirements": unmet,
    }


def _progress_payload(student):
    return {
        "student": {
            "sisId": student["sisId"],
            "name": student["name"],
            "programId": student["programId"],
            "classStanding": student["classStanding"],
            "cumulativeGpa": _cumulative_gpa(student),
        },
        "courseHistory": student["courseHistory"],
        "degreeAudit": _degree_audit(student),
        "asOf": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------
# REST contract consumed by advisor-backend/integrations/sis_client.py
# --------------------------------------------------------------------------

@app.route("/sis/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/sis/catalog")
def catalog():
    return jsonify({"courses": list(CATALOG.values())})


@app.route("/sis/programs/<program_id>")
def program(program_id):
    prog = PROGRAMS.get(program_id)
    if not prog:
        return jsonify({"error": f"Unknown program {program_id}"}), 404
    return jsonify(prog)


@app.route("/sis/students/<sis_id>")
def student(sis_id):
    s = STUDENTS.get(sis_id)
    if not s:
        return jsonify({"error": f"Unknown student {sis_id}"}), 404
    return jsonify(s)


@app.route("/sis/students/<sis_id>/progress")
def student_progress(sis_id):
    s = STUDENTS.get(sis_id)
    if not s:
        return jsonify({"error": f"Unknown student {sis_id}"}), 404
    return jsonify(_progress_payload(s))


@app.route("/sis/students/<sis_id>/grades", methods=["POST"])
def post_grades(sis_id):
    """Registrar action: post final grades for one or more courses.

    Body: [{"courseCode": "CS331", "grade": "A-", "gradePoints": 3.7, "term": "2025FA"}, ...]
    Any existing courseHistory row for that course is updated to status
    'completed'; new rows are appended. After committing, fires a
    best-effort webhook to the advisor so it can re-sync this student.
    """
    s = STUDENTS.get(sis_id)
    if not s:
        return jsonify({"error": f"Unknown student {sis_id}"}), 404

    updates = request.get_json(force=True, silent=True) or []
    with _lock:
        by_code = {c["courseCode"]: c for c in s["courseHistory"]}
        for u in updates:
            code = u.get("courseCode")
            if not code:
                continue
            row = by_code.get(code)
            if not row:
                row = {"courseCode": code, "term": u.get("term", "")}
                s["courseHistory"].append(row)
                by_code[code] = row
            row["status"] = "completed"
            row["grade"] = u.get("grade")
            row["gradePoints"] = u.get("gradePoints")
            if u.get("term"):
                row["term"] = u["term"]

    webhook_ok, webhook_error = _notify_advisor(sis_id)
    return jsonify({
        "student": _progress_payload(s),
        "webhookDelivered": webhook_ok,
        "webhookError": webhook_error,
    })


def _notify_advisor(sis_id):
    """Best-effort push to the advisor so an open portal tab updates without
    a manual sync. Never blocks the registrar action on the advisor being up."""
    headers = {"Content-Type": "application/json"}
    if SIS_WEBHOOK_TOKEN:
        headers["X-Webhook-Token"] = SIS_WEBHOOK_TOKEN
    try:
        resp = requests.post(
            ADVISOR_WEBHOOK_URL, json={"sisId": sis_id}, headers=headers, timeout=3
        )
        return resp.ok, None if resp.ok else f"advisor returned {resp.status_code}"
    except requests.RequestException as exc:
        return False, str(exc)


# --------------------------------------------------------------------------
# Registrar console — a tiny server-rendered admin page for the demo
# --------------------------------------------------------------------------

REGISTRAR_PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Registrar Console — Mock SIS</title>
  <style>
    body { font-family: -apple-system, system-ui, sans-serif; max-width: 780px; margin: 40px auto; color: #1a1a2e; }
    h1 { font-size: 20px; }
    .badge { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .completed { background: #d1fae5; color: #065f46; }
    .in_progress { background: #fef3c7; color: #92400e; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    td, th { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
    select, input[type=text] { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; }
    button { padding: 7px 14px; border-radius: 6px; border: none; background: #4338ca; color: white; font-weight: 600; cursor: pointer; }
    .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; }
    .flash { padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
    .flash.ok { background: #d1fae5; color: #065f46; }
    .flash.err { background: #fee2e2; color: #991b1b; }
    a.student-link { margin-right: 12px; }
    .muted { color: #6b7280; font-size: 13px; }
  </style>
</head>
<body>
  <h1>🏛️ Midwestern State University — Registrar Console</h1>
  <p class="muted">This is the mock system of record. Posting a grade here is what a
  registrar would do in Banner/PeopleSoft — it updates the student's official record and
  notifies any system subscribed to changes (here: the AI Course Advisor's webhook).</p>

  <div class="card">
    {% for s in students %}
      <a class="student-link" href="{{ url_for('registrar_student', sis_id=s.sisId) }}">{{ s.name }} ({{ s.sisId }})</a>
    {% endfor %}
  </div>

  {% if flash %}
    <div class="flash {{ flash.kind }}">{{ flash.text }}</div>
  {% endif %}

  {% if student %}
  <div class="card">
    <h2>{{ student.name }} — {{ student.sisId }}</h2>
    <p class="muted">{{ program.name }} · Cumulative GPA: <b>{{ gpa }}</b></p>
    <table>
      <tr><th>Course</th><th>Term</th><th>Status</th><th>Grade</th></tr>
      {% for c in student.courseHistory %}
      <tr>
        <td>{{ c.courseCode }} — {{ catalog[c.courseCode].name if c.courseCode in catalog else '?' }}</td>
        <td>{{ c.term }}</td>
        <td><span class="badge {{ c.status }}">{{ c.status }}</span></td>
        <td>{{ c.grade or '—' }}</td>
      </tr>
      {% endfor %}
    </table>

    <h3>Post a final grade</h3>
    <form method="post" action="{{ url_for('registrar_post_grade', sis_id=student.sisId) }}">
      <select name="courseCode" required>
        {% for c in postable_courses %}
          <option value="{{ c.courseCode }}">{{ c.courseCode }} ({{ c.term }}, in progress)</option>
        {% endfor %}
      </select>
      <select name="grade" required>
        {% for letter, pts in grade_options %}
          <option value="{{ letter }}" data-points="{{ pts }}">{{ letter }} ({{ pts }})</option>
        {% endfor %}
      </select>
      <button type="submit">Post grade &amp; notify advisor</button>
    </form>
  </div>
  {% endif %}
</body>
</html>
"""

GRADE_OPTIONS = [
    ("A", 4.0), ("A-", 3.7), ("B+", 3.3), ("B", 3.0), ("B-", 2.7),
    ("C+", 2.3), ("C", 2.0), ("D+", 1.3), ("D", 1.0), ("F", 0.0),
]


@app.route("/")
def registrar_home():
    return registrar_student(None)


@app.route("/registrar/<sis_id>")
def registrar_student(sis_id):
    s = STUDENTS.get(sis_id) if sis_id else None
    prog = PROGRAMS.get(s["programId"]) if s else None
    postable = [c for c in s["courseHistory"] if c["status"] == "in_progress"] if s else []
    return render_template_string(
        REGISTRAR_PAGE,
        students=STUDENTS.values(),
        student=s,
        program=prog,
        gpa=_cumulative_gpa(s) if s else None,
        catalog=CATALOG,
        postable_courses=postable,
        grade_options=GRADE_OPTIONS,
        flash=request.args.get("flash") and {
            "kind": request.args.get("kind", "ok"),
            "text": request.args.get("flash"),
        },
    )


@app.route("/registrar/<sis_id>/post-grade", methods=["POST"])
def registrar_post_grade(sis_id):
    course_code = request.form.get("courseCode")
    grade = request.form.get("grade")
    points = dict(GRADE_OPTIONS).get(grade)

    # Applies the same update the REST endpoint (POST /sis/students/:id/grades)
    # would, directly against in-memory state rather than an HTTP round-trip.
    s = STUDENTS.get(sis_id)
    if not s:
        return redirect(url_for("registrar_home"))

    with _lock:
        for row in s["courseHistory"]:
            if row["courseCode"] == course_code:
                row["status"] = "completed"
                row["grade"] = grade
                row["gradePoints"] = points
                break

    ok, err = _notify_advisor(sis_id)
    flash = f"Posted {grade} in {course_code}. " + (
        "Advisor synced ✅" if ok else f"Advisor webhook failed ⚠️ ({err}) — use Refresh from SIS in the portal instead."
    )
    return redirect(url_for(
        "registrar_student", sis_id=sis_id, flash=flash, kind="ok" if ok else "err"
    ))


@app.route("/registrar/reset", methods=["POST"])
def registrar_reset():
    """Reset all demo data back to the fixture files (handy between demo runs)."""
    _reset_state()
    return redirect(url_for("registrar_home"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(debug=True, port=port)
