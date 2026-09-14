"""LLM integration for AI Course Advisor using OpenAI gpt-4o-mini.

Provides: advisory message generation with explainability-aware prompting,
plus a conversational course-detail mode for when a student asks about one
specific course instead of asking for recommendations.
"""
import logging
import os
import random
from openai import OpenAI

from services import _parse_query_focus, _subject_prefix

logger = logging.getLogger(__name__)

_client = None
DEFAULT_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

MAX_HISTORY_TURNS = 6


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-openai-api-key-here":
            return None
        _client = OpenAI(api_key=api_key)
    return _client


def _history_messages(history):
    """Convert prior {role, content} chat turns into OpenAI message dicts,
    capped to the most recent turns so prompts stay small. Passing real
    conversation history (instead of treating every turn as a fresh call)
    is what lets the model avoid repeating itself and answer follow-ups
    like "why not the second one" or "what about its workload"."""
    if not history:
        return []
    trimmed = history[-MAX_HISTORY_TURNS:]
    messages = []
    for turn in trimmed:
        role = turn.get('role')
        content = (turn.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            messages.append({"role": role, "content": content})
    return messages


def get_advisory_message(student, query: str, recommendations: list, history: list = None) -> str:
    """Generate a personalized advisory message using gpt-4o-mini.
    Includes structured explanation factors for better explainability.
    Falls back to a templated message if OPENAI_API_KEY is not configured.
    """
    client = _get_client()
    if client is None:
        return _fallback_message(student, query, recommendations)

    course_lines = []
    for c in recommendations:
        line = (
            f"- {c.get('course_number', '')} – {c.get('course_name', '')} "
            f"({c.get('units', 3)} units)"
        )
        if not c.get('eligible', True):
            line += " [prerequisites needed]"

        factors = c.get('explanationFactors', [])
        if factors:
            factor_strs = [f"{f['type']}: {f['description']}" for f in factors if f.get('points', 0) != 0]
            if factor_strs:
                line += f"  Factors: {'; '.join(factor_strs)}"

        pred = c.get('predictedGrade')
        if pred:
            line += f"  [Predicted: {pred['predictedLetter']}]"

        course_lines.append(line)

    course_block = "\n".join(course_lines) or "No courses matched your current profile."

    completed = student.to_dict().get("completedCourses", [])
    current = student.to_dict().get("currentCourses", [])

    system_prompt = (
        "You are a friendly and knowledgeable academic advisor in an ongoing chat-style "
        "conversation. Answer their actual question first: mirror concrete asks (subject codes "
        "like EMGT/ENGR, \"non-CSEN\", topics they named). "
        "Keep your reply concise (3-6 sentences), warm, and specific. "
        "Do not list or re-describe the courses — that appears separately — but do relate your "
        "reasoning to how these picks respond to what they typed. "
        "Use the scoring factors when explaining WHY (prerequisites, peer patterns, predicted grades). "
        "If a course might lower their GPA, briefly mention the trade-off. "
        "This is a multi-turn conversation: look at the earlier turns before writing your reply, and "
        "vary your opening line and phrasing rather than reusing the same sentence structure you or "
        "the student have already seen — treat each reply as a continuation, not a reset."
    )

    # If the student named specific subjects but none of the recommended
    # courses are actually in those subjects, tell the model plainly instead
    # of letting it present unrelated courses as if they satisfy the ask.
    query_focus = _parse_query_focus(query)
    if query_focus and query_focus['include_prefixes']:
        rec_prefixes = set()
        for c in recommendations:
            rec_prefixes.add(_subject_prefix(c.get('course_number', '')))
            for alt in c.get('alt_codes', []) or []:
                rec_prefixes.add(_subject_prefix(alt))
        if not (rec_prefixes & query_focus['include_prefixes']):
            requested = '/'.join(sorted(query_focus['include_prefixes']))
            system_prompt += (
                f" IMPORTANT: the student specifically asked about {requested} courses, but none of the "
                f"courses below are actually in that subject. Say this plainly up front (e.g. \"there aren't "
                f"any {requested} courses that fit right now\"), then explain why the alternatives below are "
                f"still worth considering. Do not present them as if they satisfy the {requested} request."
            )

    user_content = (
        f"Student: {student.name}, {student.year} studying {student.major}.\n"
        f"University: {student.university or 'not specified'}.\n"
        f"Program: {student.program_enrolled or 'not specified'}.\n"
        f"Interests: {', '.join(student.interests or []) or 'not specified'}.\n"
        f"Career goals: {student.career_goals or 'not specified'}.\n"
        f"Current GPA: {student.program_gpa or 'not available'}.\n"
        f"Completed courses: {', '.join(completed) or 'none yet'}.\n"
        f"Currently taking: {', '.join(current) or 'none'}.\n\n"
        f"Their question: \"{query}\"\n\n"
        f"Top recommended courses (with scoring factors):\n{course_block}"
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *_history_messages(history),
                {"role": "user", "content": user_content},
            ],
            max_tokens=300,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("OpenAI advisory call failed: %s", e)
        return _fallback_message(student, query, recommendations)


def get_course_detail_message(student, query: str, course: dict, history: list = None) -> str:
    """Generate a conversational, deep-dive answer about ONE specific course the
    student asked about by name/code, instead of framing the reply around a
    ranked list of recommendations."""
    client = _get_client()
    if client is None:
        return _fallback_course_detail_message(student, course)

    system_prompt = (
        "You are a friendly, knowledgeable academic advisor having an ongoing chat with a student "
        "who just asked about ONE specific course. Answer conversationally, like you're describing "
        "the course to them in person: what it actually covers, what kind of work to expect, and how "
        "it fits (or doesn't) their interests, career goals, and prerequisite status. "
        "This is not a recommendation list — do not present alternative courses. "
        "Keep it to 3-6 sentences, concrete and specific to this course's real description and level, "
        "and end by inviting a natural follow-up (e.g. about workload, prerequisites, or what comes after it) "
        "rather than repeating a stock closing line. "
        "Vary your phrasing from earlier turns in this conversation instead of reusing the same sentence shapes."
    )

    prereq_note = (
        "already completed" if course.get('status') == 'completed'
        else "currently enrolled in it" if course.get('status') == 'current'
        else "eligible to take it now" if course.get('eligible')
        else f"missing prerequisites: {', '.join(course.get('missingPrerequisites') or []) or 'unclear from the catalog'}"
    )
    pred = course.get('predictedGrade')
    pred_note = f"Predicted grade if taken now: {pred['predictedLetter']} (~{pred['predictedGPA']} GPA)." if pred else ""

    user_content = (
        f"Student: {student.name}, {student.year} studying {student.major}.\n"
        f"Interests: {', '.join(student.interests or []) or 'not specified'}.\n"
        f"Career goals: {student.career_goals or 'not specified'}.\n"
        f"Current GPA: {student.program_gpa or 'not available'}.\n\n"
        f"Their question: \"{query}\"\n\n"
        f"Course: {course.get('course_number')} - {course.get('course_name')} ({course.get('units', 3)} units)\n"
        f"Level: {course.get('level') or 'not specified'}\n"
        f"Department: {course.get('department') or 'not specified'}\n"
        f"Description: {course.get('description') or 'No catalog description available.'}\n"
        f"Prerequisites: {', '.join(course.get('prerequisites') or []) or 'none'}\n"
        f"Student status: {prereq_note}\n"
        f"{pred_note}"
    )

    try:
        response = client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *_history_messages(history),
                {"role": "user", "content": user_content},
            ],
            max_tokens=300,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("OpenAI course-detail call failed: %s", e)
        return _fallback_course_detail_message(student, course)


_FALLBACK_OPENERS = [
    "Based on your profile as a {year} in {program},",
    "Looking at where you're at as a {year} in {program},",
    "Given your progress so far as a {year} in {program},",
    "Taking your background as a {year} in {program} into account,",
]


def _fallback_message(student, query: str, recommendations: list) -> str:
    count = len(recommendations)
    q = (query or '').strip()
    query_note = f' regarding "{q}",' if q else ''

    opener = random.choice(_FALLBACK_OPENERS).format(
        year=student.year, program=student.program_enrolled or student.major,
    )
    base = f"{opener}{query_note} I've surfaced {count} course{'s' if count != 1 else ''} that fit what you asked."

    notes = []
    collab_courses = [
        c for c in recommendations
        if any(f.get('type') == 'collaborative' for f in c.get('explanationFactors', []))
    ]
    if collab_courses:
        notes.append("Students with similar backgrounds frequently chose these courses.")

    interest_courses = [
        c for c in recommendations
        if any(f.get('type') == 'interest' for f in c.get('explanationFactors', []))
    ]
    if interest_courses:
        notes.append("A few of these line up directly with the interests on your profile.")

    warned = [c for c in recommendations if any(f.get('type') == 'gpa_warning' for f in c.get('explanationFactors', []))]
    if warned:
        notes.append("One or two could be a tougher grade for you, so weigh that against how much you want the material.")

    ineligible = [c for c in recommendations if not c.get('eligible', True)]
    if ineligible:
        notes.append(f"{len(ineligible)} of these still need a prerequisite first, so check that column before you register.")

    note = f" {random.choice(notes)}" if notes else ""
    return f"{base}{note} Check out the recommendations below!"


def _fallback_course_detail_message(student, course: dict) -> str:
    """No-API-key fallback for course-detail questions. Built straight from the
    course's own catalog data, so it's naturally specific to that course rather
    than a generic wrapper sentence repeated for every query."""
    name = course.get('course_name') or course.get('course_number')
    number = course.get('course_number')
    units = course.get('units', 3)
    level = course.get('level')
    description = (course.get('description') or '').strip()
    prereqs = course.get('prerequisites') or []

    lines = [f"{number} – {name} is a {units}-unit course" + (f" ({level})." if level else ".")]

    if description:
        lines.append(description)

    if course.get('status') == 'completed':
        lines.append("You've already completed this one.")
    elif course.get('status') == 'current':
        lines.append("You're currently enrolled in it.")
    elif course.get('eligible'):
        lines.append("You've met the prerequisites, so you're eligible to take it now.")
    else:
        missing = course.get('missingPrerequisites') or []
        if missing:
            lines.append(f"You'd need to complete {', '.join(missing)} first.")
        elif prereqs:
            lines.append(f"Prerequisites: {', '.join(prereqs)}.")

    pred = course.get('predictedGrade')
    if pred:
        lines.append(f"Based on your history, students with a similar GPA tend to land around a {pred['predictedLetter']}.")

    return " ".join(lines)
