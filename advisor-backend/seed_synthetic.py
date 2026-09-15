"""Synthetic background students for collaborative filtering & grade prediction.

The two "real" students in this demo (Jordan Rivera, Avery Chen) come from
the mock SIS via integrations/sis_client.py. But collaborative.py needs a
population of students with overlapping course history to find peer
patterns in, and grade_predictor.py needs at least 3 completed enrollments
per course to predict a grade — a fresh SIS with two students can't supply
either. This mirrors what the standalone project's seed.py did with 30
synthetic students, except it builds enrollment paths from whatever courses
are already in the local `courses` table (synced from the SIS at startup)
instead of a hardcoded course list, so it stays in sync with the SIS catalog
automatically.
"""
import random

from models import Course, Student, StudentCourse, db

_FIRST_NAMES = [
    "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn", "Dakota", "Reese",
    "Cameron", "Skyler", "Emerson", "Finley", "Rowan", "Sage", "Parker",
]
_LAST_NAMES = [
    "Lee", "Patel", "Garcia", "Kim", "Nguyen", "Chen", "Wilson", "Martinez",
    "Anderson", "Thomas", "Jackson", "White", "Harris", "Clark", "Lewis",
]
_INTEREST_POOLS = [
    ["Machine Learning", "AI"],
    ["Web Development", "Frontend"],
    ["Databases", "Data Management"],
    ["Networking", "Systems"],
    ["Mathematics", "Statistics"],
]
_CAREER_POOLS = [
    "Software Engineer", "Machine Learning Engineer", "Data Scientist",
    "Full-Stack Web Developer", "Backend Engineer", "Data Engineer",
]

SYNTHETIC_COUNT = 18


def _grade_for(base_gpa):
    gpa = max(0.0, min(4.0, base_gpa + random.gauss(0, 0.4)))
    gpa = round(gpa, 2)
    if gpa >= 3.85:
        return "A", gpa
    if gpa >= 3.5:
        return "A-", gpa
    if gpa >= 3.15:
        return "B+", gpa
    if gpa >= 2.85:
        return "B", gpa
    if gpa >= 2.5:
        return "B-", gpa
    if gpa >= 2.15:
        return "C+", gpa
    return "C", gpa


def run_if_needed():
    if Student.query.filter_by(is_synthetic=True).first():
        return  # already seeded

    courses = Course.query.all()
    if not courses:
        return  # catalog hasn't synced from the SIS yet

    prereq_map = {c.id: set(c.prerequisites or []) for c in courses}
    all_ids = [c.id for c in courses]

    random.seed(42)

    def valid(completed, cid):
        return prereq_map.get(cid, set()).issubset(completed)

    def build_path():
        completed = set()
        available = [cid for cid in all_ids if not prereq_map.get(cid)]
        path = []
        target_len = random.randint(3, min(7, len(all_ids)))
        while len(path) < target_len and available:
            pick = random.choice(available)
            path.append(pick)
            completed.add(pick)
            available = [cid for cid in all_ids if cid not in completed and valid(completed, cid)]
        return path

    for i in range(SYNTHETIC_COUNT):
        base_gpa = random.uniform(2.6, 3.9)
        first, last = _FIRST_NAMES[i % len(_FIRST_NAMES)], _LAST_NAMES[i % len(_LAST_NAMES)]
        student = Student(
            email=f"synthetic{i + 1}@scu.example.edu",
            name=f"{first} {last}",
            university="Santa Clara University",
            program_enrolled="MS Computer Science and Engineering",
            year=random.choice(["Sophomore", "Junior", "Senior"]),
            interests=random.choice(_INTEREST_POOLS),
            career_goals=random.choice(_CAREER_POOLS),
            is_synthetic=True,
            onboarding_completed=True,
        )
        db.session.add(student)
        db.session.flush()

        for course_id in build_path():
            letter, gpa = _grade_for(base_gpa)
            db.session.add(StudentCourse(
                student_id=student.id, course_id=course_id, status='completed',
                final_letter=letter, course_gpa=gpa, grade_points=gpa,
            ))

    db.session.commit()
