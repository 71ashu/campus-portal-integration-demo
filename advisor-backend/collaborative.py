"""Item-based collaborative filtering using co-enrollment patterns."""
from collections import defaultdict
from models import StudentCourse


def get_collaborative_scores(student_id, completed_ids, candidate_course_ids):
    """Compute collaborative filtering scores for candidate courses.

    For each candidate, counts how many students with >= 2 shared completed courses
    also completed the candidate. Returns a dict:
        {course_id: (ratio, explanation_string)}
    where ratio is between 0.0 and 1.0.
    """
    all_enrollments = StudentCourse.query.filter_by(status='completed').all()

    student_courses = defaultdict(set)
    for e in all_enrollments:
        if e.student_id != student_id:
            student_courses[e.student_id].add(e.course_id)

    completed = set(completed_ids)
    candidates = set(candidate_course_ids)
    scores = {}

    for candidate_id in candidates:
        similar_count = 0
        took_candidate = 0

        for sid, courses in student_courses.items():
            overlap = courses & completed
            if len(overlap) >= 2:
                similar_count += 1
                if candidate_id in courses:
                    took_candidate += 1

        if similar_count > 0:
            ratio = took_candidate / similar_count
            scores[candidate_id] = (
                round(ratio, 3),
                f"{took_candidate} of {similar_count} students with similar courses also took this"
            )

    return scores
