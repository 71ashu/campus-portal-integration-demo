"""Adapter between the mock SIS/degree-audit service and the advisor's own
domain model.

This module is the entire integration surface. Nothing in services.py,
knowledge_graph.py, collaborative.py, or grade_predictor.py knows the SIS
exists — they only ever read Course / Program / Student / StudentCourse rows
from the local database, exactly as they did in the standalone project. The
functions here are what keep those rows in sync with the system of record.
"""
from datetime import datetime

import requests

from config import Config
from models import Course, Program, ProgramCourse, Student, StudentCourse, db


def fetch_catalog():
    resp = requests.get(f"{Config.SIS_BASE_URL}/sis/catalog", timeout=5)
    resp.raise_for_status()
    return resp.json()["courses"]


def fetch_program(program_id):
    resp = requests.get(f"{Config.SIS_BASE_URL}/sis/programs/{program_id}", timeout=5)
    resp.raise_for_status()
    return resp.json()


def fetch_student_progress(sis_id):
    resp = requests.get(f"{Config.SIS_BASE_URL}/sis/students/{sis_id}/progress", timeout=5)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def sync_catalog_and_program(program_id=None):
    """Upsert the course catalog and one degree program from the SIS.

    Idempotent — safe to call on every app startup and on every student sync.
    This is what `seed.py` did with hardcoded Python literals in the
    standalone project; here the same Course/Program rows are populated from
    an external HTTP service instead.
    """
    program_id = program_id or Config.SIS_PROGRAM_ID

    for c in fetch_catalog():
        course = Course.query.get(c["id"])
        if not course:
            course = Course(id=c["id"])
            db.session.add(course)
        course.name = c["name"]
        course.units = c.get("units", 3)
        course.level = c.get("level", "")
        course.description = c.get("description", "")
        course.department = c.get("department", "")
        course.prerequisites = c.get("prerequisites", [])
        course.topics = c.get("topics", [])

    program_payload = fetch_program(program_id)
    program = Program.query.get(program_payload["id"])
    if not program:
        program = Program(program_id=program_payload["id"])
        db.session.add(program)
    program.program_name = program_payload["name"]
    program.degree_type = program_payload.get("degreeType", "")
    program.department = program_payload.get("department", "")
    program.total_units_required = program_payload.get("totalUnitsRequired")
    program.minimum_gpa = program_payload.get("minimumGpa")
    program.requirements = {
        "catalog_year": program_payload.get("catalogYear", ""),
        # Real MS-CSEN rule from SCU's Graduate Engineering Bulletin: at most
        # 6 units of EMGT electives count toward the degree. services.py
        # already has this cap logic (`non_csen_elective_caps`); it just had
        # nothing real to enforce until the catalog carried real EMGT courses.
        "non_csen_elective_caps": program_payload.get("nonCsenElectiveCaps", {}),
    }

    all_course_ids = set(program_payload.get("coreCourseIds", [])) | set(
        program_payload.get("electiveCourseIds", [])
    )
    existing_links = {
        pc.course_id for pc in ProgramCourse.query.filter_by(program_id=program.program_id).all()
    }
    for cid in all_course_ids - existing_links:
        db.session.add(ProgramCourse(program_id=program.program_id, course_id=cid))

    db.session.commit()
    return program.program_id


def sync_student(student, payload=None):
    """Pull this student's academic record + degree audit from the SIS and
    overwrite the advisor's local copy of it.

    Returns the raw SIS payload (useful for surfacing `asOf` / audit details
    to the caller) or None if the SIS doesn't know this student.
    """
    if not student.sis_id:
        raise ValueError("Student has no sis_id to sync from")

    payload = payload or fetch_student_progress(student.sis_id)
    if payload is None:
        return None

    sis_student = payload["student"]
    audit = payload["degreeAudit"]

    # Make sure the catalog/program this payload references are loaded before
    # attaching StudentCourse rows to them.
    sync_catalog_and_program(sis_student.get("programId"))

    program = Program.query.get(sis_student.get("programId"))
    student.name = sis_student.get("name", student.name)
    student.program_enrolled = program.program_name if program else student.program_enrolled
    student.year = sis_student.get("classStanding", student.year)
    student.program_gpa = sis_student.get("cumulativeGpa", student.program_gpa)
    student.sis_synced_at = datetime.utcnow()
    student.sis_unmet_requirements = audit.get("unmetRequirements", [])

    _replace_enrollments(student, payload["courseHistory"])

    db.session.commit()
    return payload


def _replace_enrollments(student, course_history):
    """Mirror the SIS's courseHistory into StudentCourse rows exactly:
    completed/in-progress there means completed/current here, and a course
    that disappears from the SIS record disappears from ours too."""
    existing = {
        sc.course_id: sc for sc in StudentCourse.query.filter_by(student_id=student.id).all()
    }
    seen_ids = set()

    for entry in course_history:
        course_id = entry["courseCode"]
        if not Course.query.get(course_id):
            continue  # defensive: course not in the synced catalog
        seen_ids.add(course_id)

        status = 'completed' if entry["status"] == 'completed' else 'current'
        row = existing.get(course_id)
        if not row:
            row = StudentCourse(student_id=student.id, course_id=course_id, status=status)
            db.session.add(row)
        else:
            row.status = status

        grade_points = entry.get("gradePoints")
        row.final_letter = entry.get("grade")
        row.grade_points = grade_points
        row.course_gpa = grade_points

    for course_id, row in existing.items():
        if course_id not in seen_ids:
            db.session.delete(row)


def find_student_by_sis_id(sis_id):
    return Student.query.filter_by(sis_id=sis_id).first()


def provision_student(sis_id):
    """Create the local Student shell for a campus ID the advisor hasn't
    seen before, then hydrate it immediately from the SIS. Used by the mock
    SSO endpoint on first login."""
    payload = fetch_student_progress(sis_id)
    if payload is None:
        return None, None

    sis_student = payload["student"]
    student = Student(
        email=f"{sis_id.lower()}@scu.example.edu",
        name=sis_student.get("name", sis_id),
        university="Santa Clara University",
        program_enrolled="",
        interests=[],
        career_goals="",
        # The onboarding quiz exists to cold-start a student with zero
        # history; a student arriving via SSO already has a full academic
        # record from the SIS, so there is nothing to bootstrap.
        onboarding_completed=True,
        sis_id=sis_id,
    )
    db.session.add(student)
    db.session.flush()  # assign student.id before sync_student writes StudentCourse rows

    sync_student(student, payload=payload)
    return student, payload
