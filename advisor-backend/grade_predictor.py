"""Grade prediction based on historical grade distributions."""
from models import StudentCourse, db
from sqlalchemy import func


def predict_grade(student_gpa, course_id):
    """Predict a student's likely grade in a course.

    Uses the course's historical average GPA and the student's overall GPA
    to estimate performance via linear adjustment.
    Returns None if insufficient data (< 3 completed enrollments with grades).
    """
    stats = db.session.query(
        func.avg(StudentCourse.course_gpa),
        func.count(StudentCourse.id)
    ).filter_by(
        course_id=course_id, status='completed'
    ).filter(
        StudentCourse.course_gpa.isnot(None)
    ).first()

    course_avg, sample_size = stats
    if not course_avg or sample_size < 3:
        return None

    course_avg = float(course_avg)
    predicted = course_avg + 0.6 * (student_gpa - course_avg)
    predicted = max(0.0, min(4.0, round(predicted, 2)))

    letter = _gpa_to_letter(predicted)

    if course_avg < 2.7:
        difficulty = "very challenging"
    elif course_avg < 3.0:
        difficulty = "challenging"
    elif course_avg < 3.5:
        difficulty = "moderate"
    else:
        difficulty = "accessible"

    return {
        "predictedGPA": predicted,
        "predictedLetter": letter,
        "courseAvgGPA": round(course_avg, 2),
        "sampleSize": sample_size,
        "difficultyIndicator": difficulty,
    }


def _gpa_to_letter(gpa):
    if gpa >= 3.85:
        return "A"
    elif gpa >= 3.5:
        return "A-"
    elif gpa >= 3.15:
        return "B+"
    elif gpa >= 2.85:
        return "B"
    elif gpa >= 2.5:
        return "B-"
    elif gpa >= 2.15:
        return "C+"
    elif gpa >= 1.85:
        return "C"
    else:
        return "C-"
