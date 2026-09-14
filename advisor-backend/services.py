"""Business logic for recommendations and degree progress.

Integrates: knowledge graph, collaborative filtering, GPA prediction,
and structured explainability.
"""
import re
from models import Course, Program, ProgramCourse, Student, StudentCourse, db
from knowledge_graph import get_reachable_courses, get_path_to_course
from collaborative import get_collaborative_scores
from grade_predictor import predict_grade

REQUIRED_CREDITS = 120

# Subject prefixes often used in catalogs (SCU-style EMGT/ENGR/CSEN, etc.).
KNOWN_SUBJECT_PREFIXES = frozenset({
    'AMTH', 'BIO', 'CHEM', 'COEN', 'CSEN', 'CSCI', 'ECON', 'EE', 'ELEN',
    'EMGT', 'ENGR', 'ENG', 'MATH', 'MECH', 'PHYS', 'PSYC', 'STAT',
})

CS_SUBJECT_PREFIXES = frozenset({'CS', 'CSEN', 'COEN', 'CSCI'})

QUERY_STOPWORDS = frozenset({
    'a', 'all', 'also', 'am', 'an', 'and', 'any', 'are', 'as', 'at', 'be',
    'been', 'being', 'both', 'but', 'by', 'can', 'could', 'did', 'do',
    'does', 'each', 'few', 'for', 'from', 'further', 'had', 'has', 'have',
    'her', 'here', 'hers', 'him', 'his', 'how', 'i', 'if', 'in', 'into',
    'is', 'it', 'its', 'just', 'like', 'may', 'me', 'might', 'more', 'most',
    'must', 'my', 'need', 'no', 'nor', 'not', 'now', 'of', 'off', 'on',
    'once', 'only', 'or', 'other', 'our', 'ours', 'out', 'over', 'own',
    'please', 'same', 'she', 'should', 'so', 'some', 'such', 'tell',
    'than', 'that', 'the', 'their', 'them', 'then', 'there', 'these',
    'they', 'this', 'those', 'through', 'to', 'too', 'under', 'until',
    'very', 'want', 'was', 'we', 'were', 'what', 'when', 'where', 'which',
    'who', 'whom', 'why', 'will', 'with', 'would', 'you', 'your',
    'course', 'courses', 'class', 'classes', 'semester', 'term', 'year',
    'next', 'recommend', 'recommendations', 'looking', 'help', 'show',
    'give', 'find', 'suggest', 'about', 'instead', 'rather', 'something',
    'anything', 'everything', 'non',
})


def _subject_prefix(course_id):
    """Leading alphabetic subject code from catalog id (e.g. CSEN 342 -> CSEN, CS101 -> CS)."""
    if not course_id:
        return ''
    s = str(course_id).strip().upper()
    m = re.match(r'^([A-Z]+)', s)
    return m.group(1) if m else ''


def _course_prefixes(course):
    """All subject prefixes a course is known under, including cross-listed alt codes
    (e.g. EMGT 269 is also ENGR 269)."""
    prefixes = {_subject_prefix(course.id)}
    for alt in (course.alt_codes or []):
        prefixes.add(_subject_prefix(alt))
    prefixes.discard('')
    return prefixes


def _course_search_blob(course):
    parts = [course.id or '', course.name or '', course.description or '', course.department or '']
    for t in course.topics or []:
        parts.append(str(t))
    return ' '.join(parts).lower()


def _parse_query_focus(query):
    """Extract subject inclusion/exclusion and keywords so rankings follow the user's question."""
    if not (query or '').strip():
        return None

    raw = query.strip()
    ql = raw.lower()
    ql = re.sub(r'(non|outside|excluding|without|avoid|skip)(csen|csci|coen)', r'\1 \2', ql)

    exclude_prefixes = set()

    if re.search(r'\b(?:non|outside|excluding|without|avoid|skip)\s*[-]?\s*csen\b', ql):
        exclude_prefixes.add('CSEN')
        # Demo catalogs often use CS* ids instead of CSEN; treat as same intent.
        exclude_prefixes.update(CS_SUBJECT_PREFIXES)

    if re.search(
        r'\b(?:non|outside|excluding|without|avoid|skip)\s*[-]?\s*(?:computer\s+science|csci)\b',
        ql,
    ):
        exclude_prefixes.update(CS_SUBJECT_PREFIXES)

    if re.search(r'\b(?:non|outside|excluding|without|avoid|skip)\s*[-]?\s*cs\b(?![a-z0-9])', ql):
        exclude_prefixes.update(CS_SUBJECT_PREFIXES)

    tokens_upper = set(re.findall(r'\b([A-Z]{2,8})\b', re.sub(r'[/]', ' ', raw).upper()))
    include_prefixes = {
        t for t in tokens_upper
        if t in KNOWN_SUBJECT_PREFIXES and t not in exclude_prefixes
    }

    semantic_tokens = []
    for w in re.findall(r'[a-z0-9]+', ql):
        if len(w) < 3 or w in QUERY_STOPWORDS:
            continue
        if w in {x.lower() for x in KNOWN_SUBJECT_PREFIXES}:
            continue
        semantic_tokens.append(w)

    return {
        'exclude_prefixes': exclude_prefixes,
        'include_prefixes': include_prefixes,
        'semantic_tokens': semantic_tokens,
    }


def find_course_by_query(query):
    """Find a single course explicitly named by code in free-text (e.g. "tell me
    about CSEN 342" or "what's CS101 like?"). Returns None if the query doesn't
    name a specific, known course — that's the signal to fall back to ranking
    the whole catalog instead of answering about one course."""
    if not (query or '').strip():
        return None

    tokens = re.findall(r'\b[A-Za-z]{2,6}\s?-?\s?\d{3}[A-Za-z]?\b', query)
    if not tokens:
        return None

    lookup = {}
    for course in Course.query.all():
        lookup[course.id.replace(' ', '').upper()] = course
        for alt in (course.alt_codes or []):
            lookup[alt.replace(' ', '').upper()] = course

    for token in tokens:
        normalized = re.sub(r'[\s-]+', '', token).upper()
        if normalized in lookup:
            return lookup[normalized]
    return None


def get_course_detail(student, course):
    """Build a single-course payload (same shape as a recommendation item) for
    conversational Q&A about one specific course: is the student eligible,
    have they already taken it, what would they likely score."""
    completed_ids = {
        sc.course_id for sc in
        StudentCourse.query.filter_by(student_id=student.id, status='completed').all()
    }
    current_ids = {
        sc.course_id for sc in
        StudentCourse.query.filter_by(student_id=student.id, status='current').all()
    }

    status = 'completed' if course.id in completed_ids else 'current' if course.id in current_ids else None

    reachable = get_reachable_courses(completed_ids)
    prereqs_met = course.id in reachable
    missing_prereqs = []
    if not prereqs_met:
        path = get_path_to_course(completed_ids, course.id)
        missing_prereqs = [
            Course.query.get(cid).name for cid in path
            if cid != course.id and Course.query.get(cid)
        ]

    student_gpa = student.program_gpa or 0.0
    grade_prediction = (
        predict_grade(student_gpa, course.id)
        if student_gpa > 0 and status is None else None
    )

    if status == 'completed':
        match_reason = 'Already on your completed courses list'
    elif status == 'current':
        match_reason = "You're currently taking this"
    elif prereqs_met:
        match_reason = 'All prerequisites completed'
    else:
        match_reason = f"Still need: {', '.join(missing_prereqs)}" if missing_prereqs else 'Prerequisites not yet met'

    return {
        **course.to_dict(),
        'eligible': prereqs_met,
        'status': status,
        'missingPrerequisites': missing_prereqs,
        'matchReason': match_reason,
        'explanationFactors': [],
        'predictedGrade': grade_prediction,
    }


def _serialize_progress_course(enrollment):
    course = Course.query.get(enrollment.course_id)
    if not course:
        return None
    return {
        'courseId': enrollment.course_id,
        'courseName': course.name,
        'units': course.units,
        'status': enrollment.status,
        'finalScore': enrollment.final_score,
        'finalLetter': enrollment.final_letter,
        'courseGPA': enrollment.course_gpa if enrollment.course_gpa is not None else enrollment.grade_points,
    }


def _normalize_program_text(value):
    normalized = (value or '').lower().replace('&', ' and ')
    normalized = re.sub(r'\band\b', ' ', normalized)
    return re.sub(r'[^a-z0-9]+', '', normalized)


def _resolve_program_for_student(student):
    program_text = (student.program_enrolled or '').strip()
    if not program_text:
        return None

    direct_match = Program.query.filter(
        Program.program_name.ilike(program_text)
    ).first()
    if direct_match:
        return direct_match

    normalized_target = _normalize_program_text(program_text)
    for program in Program.query.all():
        normalized_name = _normalize_program_text(program.program_name)
        normalized_id = _normalize_program_text(program.program_id)
        if normalized_target and (
            normalized_target in normalized_name
            or normalized_name in normalized_target
            or normalized_target in normalized_id
            or normalized_id in normalized_target
        ):
            return program
    return None


def _build_program_requirement_items(program):
    if not program:
        return []

    requirements = []
    if program.total_units_required:
        requirements.append(f"{program.total_units_required} total units required")
    if program.minimum_gpa:
        requirements.append(f"Minimum GPA: {program.minimum_gpa:.2f}")

    linked_courses = (
        db.session.query(Course)
        .join(ProgramCourse, ProgramCourse.course_id == Course.id)
        .filter(ProgramCourse.program_id == program.program_id)
        .all()
    )
    core_courses = [c for c in linked_courses if (c.level or '').lower() == 'graduate core']
    core_units = sum((c.units or 0) for c in core_courses)

    if core_courses:
        requirements.append(
            f"{len(core_courses)} graduate core courses ({core_units} units)"
        )
        elective_units = max((program.total_units_required or 0) - core_units, 0)
        if elective_units:
            requirements.append(f"At least {elective_units} units of graduate electives")

    nested_requirements = program.requirements or {}
    if isinstance(nested_requirements, dict):
        for key, value in nested_requirements.items():
            if isinstance(value, (str, int, float)) and value not in ('', None):
                requirements.append(f"{str(key).replace('_', ' ').title()}: {value}")

    return requirements


def calculate_program_gpa(student):
    """Compute weighted GPA from completed courses with grade points."""
    completed = StudentCourse.query.filter_by(student_id=student.id, status='completed').all()
    total_units = 0
    total_quality_points = 0.0

    for sc in completed:
        per_course_gpa = sc.course_gpa if sc.course_gpa is not None else sc.grade_points
        if per_course_gpa is None:
            continue
        course = Course.query.get(sc.course_id)
        if not course or not course.units:
            continue
        total_units += course.units
        total_quality_points += per_course_gpa * course.units

    if total_units == 0:
        return 0.0
    return round(total_quality_points / total_units, 2)


def get_degree_progress(student):
    """Calculate degree progress for a student."""
    completed = StudentCourse.query.filter_by(student_id=student.id, status='completed').all()
    current = StudentCourse.query.filter_by(student_id=student.id, status='current').all()
    
    total_credits = 0
    for sc in completed + current:
        course = Course.query.get(sc.course_id)
        if course:
            total_credits += course.units

    matched_program = _resolve_program_for_student(student)
    required_credits = (
        matched_program.total_units_required
        if matched_program and matched_program.total_units_required
        else REQUIRED_CREDITS
    )
    progress_pct = min((total_credits / required_credits) * 100, 100) if required_credits else 0
    major_credits = total_credits if matched_program else int(total_credits * 0.6)
    requirement_items = _build_program_requirement_items(matched_program)
    computed_gpa = calculate_program_gpa(student)
    completed_with_grades = [
        data for data in (_serialize_progress_course(sc) for sc in completed) if data is not None
    ]
    current_with_grades = [
        data for data in (_serialize_progress_course(sc) for sc in current) if data is not None
    ]
    
    return {       
        'totalCredits': total_credits,
        'requiredCredits': required_credits,
        'progressPercentage': round(progress_pct, 1),
        'majorCredits': major_credits,
        'completedCoursesCount': len(completed),
        'programGPA': student.program_gpa if student.program_gpa is not None else computed_gpa,
        'programName': matched_program.program_name if matched_program else (student.program_enrolled or ''),
        'programDegreeType': matched_program.degree_type if matched_program else '',
        'programRequirementItems': requirement_items,
        'completedCourses': completed_with_grades,
        'currentCourses': current_with_grades,
    }


def get_recommendations(student, query='', limit=6):
    """Get course recommendations with multi-signal scoring and structured explanations.

    Scoring signals:
      - Prerequisite eligibility (knowledge graph)          +50
      - Interest/topic match                                +30
      - Collaborative filtering (peer enrollment patterns)  +25 * ratio
      - Query alignment (subject codes, exclusions, keywords)
      - Legacy ML/AI query phrases                           +40 (unless excluded CS subjects)
      - GPA prediction penalty (if course would hurt GPA)   -10
    """
    completed_ids = set(
        sc.course_id for sc in 
        StudentCourse.query.filter_by(student_id=student.id, status='completed').all()
    )
    current_ids = set(
        sc.course_id for sc in 
        StudentCourse.query.filter_by(student_id=student.id, status='current').all()
    )
    taken = completed_ids | current_ids
    interests = set(student.interests or [])
    query_focus = _parse_query_focus(query)

    # Use knowledge graph for eligibility
    reachable = get_reachable_courses(completed_ids)

    # Scope candidates to the student's actual program requirements (real
    # CSEN + approved non-CSEN electives) rather than the entire catalog.
    # Falls back to the full catalog if the program isn't resolved or has
    # no linked courses yet (e.g. programs we haven't populated electives for).
    program = _resolve_program_for_student(student)
    program_requirements = (program.requirements or {}) if program else {}
    program_course_ids = None
    if program:
        program_course_ids = {
            pc.course_id for pc in
            ProgramCourse.query.filter_by(program_id=program.program_id).all()
        }

    if program_course_ids:
        all_courses = Course.query.filter(Course.id.in_(program_course_ids)).all()
    else:
        all_courses = Course.query.all()

    candidate_ids = [c.id for c in all_courses if c.id not in taken]

    # Unit caps on certain non-CSEN elective prefixes (e.g. MS-CSEN allows at
    # most 6 units of EMGT courses). Compute remaining headroom per prefix.
    elective_caps = program_requirements.get('non_csen_elective_caps', {}) or {}
    remaining_cap_units = {}
    if elective_caps and taken:
        taken_courses = Course.query.filter(Course.id.in_(taken)).all()
        for cap_prefix, cap_units in elective_caps.items():
            used = sum(
                (c.units or 0) for c in taken_courses
                if cap_prefix in _course_prefixes(c)
            )
            remaining_cap_units[cap_prefix] = max(cap_units - used, 0)
    elif elective_caps:
        remaining_cap_units = dict(elective_caps)

    # Batch compute collaborative scores
    collab_scores = get_collaborative_scores(student.id, completed_ids, candidate_ids)

    student_gpa = student.program_gpa or 0.0

    scored = []

    for course in all_courses:
        if course.id in taken:
            continue

        score = 0
        factors = []
        prereqs_met = course.id in reachable

        # --- Prerequisite eligibility ---
        if prereqs_met:
            score += 50
            factors.append({
                "type": "prerequisite", 
                "description": "All prerequisites completed",
                "points": 50,
            })
        else:
            path = get_path_to_course(completed_ids, course.id)
            path_names = [Course.query.get(cid).name for cid in path if Course.query.get(cid) and cid != course.id]
            if path_names:
                factors.append({
                    "type": "prerequisite",
                    "description": f"Still need: {', '.join(path_names)}",
                    "points": 0,
                })

        prefix = _subject_prefix(course.id)
        prefixes = _course_prefixes(course)
        blob = _course_search_blob(course)

        # --- Non-CSEN elective unit caps (e.g. EMGT capped at 6 units) ---
        cap_exceeded_prefix = None
        for cap_prefix, remaining in remaining_cap_units.items():
            if cap_prefix in prefixes and (course.units or 0) > remaining:
                cap_exceeded_prefix = cap_prefix
                break

        if query_focus and query_focus['exclude_prefixes']:
            ep = query_focus['exclude_prefixes']
            excluded = False
            if prefixes & ep:
                excluded = True
            elif ep & CS_SUBJECT_PREFIXES:
                dept = (course.department or '').lower()
                if prefixes & CS_SUBJECT_PREFIXES or 'computer' in dept:
                    excluded = True
            if excluded:
                continue

        cs_query_excluded = (
            query_focus
            and query_focus['exclude_prefixes'] & CS_SUBJECT_PREFIXES
        )

        # --- Interest / topic match ---
        if not (cs_query_excluded and prefixes & CS_SUBJECT_PREFIXES):
            for topic in (course.topics or []):
                if topic.lower() in [i.lower() for i in interests]:
                    score += 30
                    factors.append({
                        "type": "interest",
                        "description": f"Aligns with your interest in {topic}",
                        "points": 30,
                    })
                    break

        # --- Collaborative filtering ---
        collab = collab_scores.get(course.id)
        if collab:
            ratio, explanation = collab
            collab_pts = round(25 * ratio)
            if collab_pts > 0:
                score += collab_pts
                factors.append({
                    "type": "collaborative",
                    "description": explanation,
                    "points": collab_pts,
                })

        # --- Query alignment (follow what the user asked) ---
        if query_focus:
            matched_prefixes = prefixes & query_focus['include_prefixes']
            if matched_prefixes:
                pts = 45
                score += pts
                factors.append({
                    "type": "query",
                    "description": f"Matches requested subject ({'/'.join(sorted(matched_prefixes))})",
                    "points": pts,
                })

            hits = sorted({t for t in query_focus['semantic_tokens'] if t in blob})
            if hits:
                pts = min(18 + 6 * len(hits), 42)
                score += pts
                preview = ', '.join(hits[:4])
                if len(hits) > 4:
                    preview += ', …'
                factors.append({
                    "type": "query",
                    "description": f"Aligns with your question ({preview})",
                    "points": pts,
                })

        ql = query.lower() if query else ''
        if ql and not (query_focus and query_focus['exclude_prefixes'] & CS_SUBJECT_PREFIXES):
            if any(t in ql for t in ['ml', 'machine learning', 'ai', 'artificial intelligence']):
                topic_ai = [t.lower() for t in (course.topics or [])]
                if 'machine learning' in (course.name or '').lower() or 'ai' in topic_ai:
                    score += 40
                    factors.append({
                        "type": "query",
                        "description": "Matches your ML/AI interest",
                        "points": 40,
                    })

        # --- GPA prediction ---
        grade_prediction = predict_grade(student_gpa, course.id) if student_gpa > 0 else None
        if grade_prediction:
            if grade_prediction['predictedGPA'] < student_gpa - 0.3:
                score -= 10
                factors.append({
                    "type": "gpa_warning",
                    "description": f"May lower your GPA (predicted ~{grade_prediction['predictedLetter']})",
                    "points": -10,
                })
            else:
                factors.append({
                    "type": "gpa",
                    "description": f"Predicted grade: {grade_prediction['predictedLetter']} ({grade_prediction['predictedGPA']})",
                    "points": 0,
                })

        if cap_exceeded_prefix:
            cap_units = elective_caps.get(cap_exceeded_prefix)
            factors.append({
                "type": "elective_cap",
                "description": f"Would exceed the {cap_units}-unit {cap_exceeded_prefix} elective cap for your program",
                "points": 0,
            })

        # Build top-level match reason. The elective cap is a hard blocker, so
        # it takes priority over the highest-point factor when it applies.
        if cap_exceeded_prefix:
            match_reason = factors[-1]['description']
        else:
            top_factor = max(factors, key=lambda f: f['points']) if factors else None
            match_reason = top_factor['description'] if top_factor else "Complements your academic profile"

        scored.append({
            'course': course,
            'score': score,
            'eligible': prereqs_met and not cap_exceeded_prefix,
            'matchReason': match_reason,
            'explanationFactors': factors,
            'predictedGrade': grade_prediction,
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    safe_limit = max(int(limit or 6), 1)
    top = scored[:safe_limit]

    return [
        {
            **item['course'].to_dict(),
            'eligible': item['eligible'],
            'matchReason': item['matchReason'],
            'explanationFactors': item['explanationFactors'],
            'predictedGrade': item['predictedGrade'],
        }
        for item in top
    ]
