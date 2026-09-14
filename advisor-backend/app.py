"""
AI Course Advisor — portal-integration demo backend.

Same recommendation engine as the standalone AI-Course-Advisor project
(services.py, knowledge_graph.py, collaborative.py, grade_predictor.py are
unmodified). What's different here: a student's profile, course history, and
degree audit come from the mock SIS (see ../mock-sis) via
integrations/sis_client.py, instead of from a local seed script + password
login. Auth is a mock campus SSO (POST /api/auth/sso with just a campus ID —
no password), and a webhook lets the SIS push updates when a registrar posts
a grade.
"""
from datetime import datetime

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from config import Config
from models import db, Conversation, Course, Message, Program, ProgramCourse, Student, StudentCourse
from services import get_degree_progress, get_recommendations, find_course_by_query, get_course_detail
from llm import get_advisory_message, get_course_detail_message
from knowledge_graph import get_path_to_course, get_graph_summary
from integrations import sis_client
import seed_synthetic

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True, origins=Config.CORS_ORIGINS)
db.init_app(app)


def get_current_student():
    student_id = session.get('student_id')
    if student_id:
        return Student.query.get(student_id)
    return None


def _check_webhook_token():
    if not Config.SIS_WEBHOOK_TOKEN:
        return True  # unconfigured: demo runs open, matching the README's default setup
    return request.headers.get('X-Webhook-Token') == Config.SIS_WEBHOOK_TOKEN


# ============ Auth (mock campus SSO) ============

@app.route('/api/auth/sso', methods=['POST'])
def sso():
    """Stand-in for a real SSO/LTI launch: the portal hands us a campus ID,
    we look the student up in the SIS (creating the local shell record on
    first login) and start a session. No password anywhere in this flow —
    that's the point of SSO."""
    data = request.json or {}
    sis_id = (data.get('sisId') or '').strip()
    if not sis_id:
        return jsonify({'error': 'sisId is required'}), 400

    student = sis_client.find_student_by_sis_id(sis_id)
    try:
        if student:
            sis_client.sync_student(student)
        else:
            student, payload = sis_client.provision_student(sis_id)
            if student is None:
                return jsonify({'error': f'No SIS record for campus ID {sis_id}'}), 404
    except Exception as exc:  # SIS down, network error, etc.
        app.logger.exception('SSO sync failed')
        return jsonify({'error': f'Could not reach the SIS: {exc}'}), 502

    session.permanent = True
    session['student_id'] = student.id
    return jsonify({'student': student.to_dict()})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('student_id', None)
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def me():
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'student': student.to_dict()})


# ============ SIS sync ============

@app.route('/api/sync', methods=['POST'])
def sync():
    """Manual 'Refresh from SIS' — re-pulls the current student's academic
    record and degree audit. The same code path a registrar's grade-post
    webhook triggers automatically."""
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    payload = sis_client.sync_student(student)
    if payload is None:
        return jsonify({'error': 'SIS no longer has a record for this student'}), 502

    return jsonify({
        'student': student.to_dict(),
        'progress': get_degree_progress(student),
        'syncedAt': student.sis_synced_at.isoformat() if student.sis_synced_at else None,
    })


@app.route('/api/webhooks/sis/grade-posted', methods=['POST'])
def sis_grade_webhook():
    """Called by the mock SIS registrar console right after a grade posts.
    Server-to-server — no browser session involved."""
    if not _check_webhook_token():
        return jsonify({'error': 'Invalid webhook token'}), 401

    data = request.json or {}
    sis_id = data.get('sisId')
    if not sis_id:
        return jsonify({'error': 'sisId is required'}), 400

    student = sis_client.find_student_by_sis_id(sis_id)
    if not student:
        # Nobody has logged into the portal with this campus ID yet — nothing
        # locally to update.
        return jsonify({'synced': False, 'reason': 'no local student for this sisId'})

    sis_client.sync_student(student)
    return jsonify({'synced': True})


# ============ Profile ============

@app.route('/api/profile', methods=['GET', 'PUT'])
def profile():
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    if request.method == 'GET':
        return jsonify({'student': student.to_dict()})

    # Only the fields the SIS doesn't own are editable here. Completed/current
    # courses and GPA come from the SIS sync and would just be overwritten on
    # the next sync anyway.
    data = request.json or {}
    if data.get('interests') is not None:
        student.interests = data['interests']
    if data.get('careerGoals') is not None:
        student.career_goals = data['careerGoals']

    db.session.commit()
    return jsonify({'student': student.to_dict()})


# ============ Courses ============

@app.route('/api/courses', methods=['GET'])
def get_courses():
    courses = Course.query.all()
    return jsonify({'courses': [c.to_dict() for c in courses]})


# ============ Conversations ============

def _title_from_query(query):
    text = ' '.join((query or '').strip().split())
    if not text:
        return 'New conversation'
    return text[:60] + ('…' if len(text) > 60 else '')


def _resolve_conversation(student, conversation_id):
    if conversation_id:
        convo = Conversation.query.filter_by(id=conversation_id, student_id=student.id).first()
        if not convo:
            return None, (jsonify({'error': 'Conversation not found'}), 404)
        return convo, None

    convo = Conversation(student_id=student.id)
    db.session.add(convo)
    db.session.flush()
    return convo, None


@app.route('/api/conversations', methods=['GET', 'POST'])
def conversations():
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    if request.method == 'POST':
        convo = Conversation(student_id=student.id)
        db.session.add(convo)
        db.session.commit()
        return jsonify({'conversation': convo.to_dict(include_messages=True)})

    rows = (
        Conversation.query.filter_by(student_id=student.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .all()
    )
    return jsonify({'conversations': [c.to_dict() for c in rows]})


@app.route('/api/conversations/<int:conversation_id>', methods=['GET', 'PATCH', 'DELETE'])
def conversation_detail(conversation_id):
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    convo = Conversation.query.filter_by(id=conversation_id, student_id=student.id).first()
    if not convo:
        return jsonify({'error': 'Conversation not found'}), 404

    if request.method == 'GET':
        return jsonify({'conversation': convo.to_dict(include_messages=True)})

    if request.method == 'PATCH':
        data = request.json or {}
        title = (data.get('title') or '').strip()
        if title:
            convo.title = title[:200]
            db.session.commit()
        return jsonify({'conversation': convo.to_dict()})

    db.session.delete(convo)
    db.session.commit()
    return jsonify({'success': True})


# ============ Advisor ============

@app.route('/api/recommend', methods=['POST'])
def recommend():
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json or {}
    query = data.get('query', '')

    convo, error = _resolve_conversation(student, data.get('conversationId'))
    if error:
        return error

    stored = convo.messages.all()
    history = (
        [{'role': m.role, 'content': m.content} for m in stored]
        or (data.get('history') or [])
    )

    db.session.add(Message(conversation_id=convo.id, role='user', content=query))

    named_course = find_course_by_query(query)
    if named_course:
        detail = get_course_detail(student, named_course)
        message = get_course_detail_message(student, query, detail, history=history)
        recommendations = [detail]
    else:
        recommendations = get_recommendations(student, query)
        message = get_advisory_message(student, query, recommendations, history=history)

    db.session.add(Message(
        conversation_id=convo.id, role='assistant', content=message, recommendations=recommendations,
    ))

    if convo.title in (None, '', 'New conversation') and query.strip():
        convo.title = _title_from_query(query)
    convo.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'conversationId': convo.id,
        'recommendations': recommendations,
        'message': message,
    })


@app.route('/api/progress', methods=['GET'])
def progress():
    student = get_current_student()
    if not student:
        return jsonify({'error': 'Not authenticated'}), 401

    progress_data = get_degree_progress(student)
    # Provenance fields only — get_degree_progress() itself is untouched.
    progress_data['sisSyncedAt'] = student.sis_synced_at.isoformat() if student.sis_synced_at else None
    progress_data['sisUnmetRequirements'] = student.sis_unmet_requirements or []
    return jsonify(progress_data)


# ============ Prerequisite graph ============

@app.route('/api/prerequisite-path', methods=['GET'])
def prerequisite_path():
    target = request.args.get('target')
    if not target:
        return jsonify({'error': 'target query parameter is required'}), 400

    course = Course.query.get(target)
    if not course:
        return jsonify({'error': f'Course {target} not found'}), 404

    student = get_current_student()
    completed_ids = set()
    if student:
        completed_ids = set(
            sc.course_id for sc in
            StudentCourse.query.filter_by(student_id=student.id, status='completed').all()
        )

    path = get_path_to_course(completed_ids, target)
    path_details = []
    for cid in path:
        c = Course.query.get(cid)
        if c:
            path_details.append({'courseId': c.id, 'courseName': c.name, 'completed': cid in completed_ids})

    return jsonify({'target': target, 'path': path_details})


@app.route('/api/prerequisite-graph', methods=['GET'])
def prerequisite_graph():
    return jsonify(get_graph_summary())


# ============ Programs ============

@app.route('/api/programs', methods=['GET'])
def get_programs():
    programs = Program.query.order_by(Program.program_name).all()
    return jsonify({'programs': [p.to_dict() for p in programs]})


@app.route('/api/programs/<string:program_id>', methods=['GET'])
def get_program(program_id):
    program = Program.query.get_or_404(program_id)
    linked_courses = (
        db.session.query(Course)
        .join(ProgramCourse, ProgramCourse.course_id == Course.id)
        .filter(ProgramCourse.program_id == program_id)
        .all()
    )
    result = program.to_dict()
    result['courses'] = [c.to_dict() for c in linked_courses]
    return jsonify(result)


# ============ Health ============

@app.route('/api/health', methods=['GET'])
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except Exception:
        db_status = 'disconnected'
    return jsonify({'status': 'healthy', 'database': db_status})


def bootstrap():
    """Runs once at process start: create tables, pull the catalog/program
    from the SIS, and seed background synthetic students so collaborative
    filtering and grade prediction have data on day one."""
    with app.app_context():
        db.create_all()
        try:
            sis_client.sync_catalog_and_program()
        except Exception as exc:
            app.logger.warning(
                'Could not reach the mock SIS at %s (%s). Start it first: '
                'cd mock-sis && python app.py', Config.SIS_BASE_URL, exc,
            )
            return
        seed_synthetic.run_if_needed()


if __name__ == '__main__':
    bootstrap()
    debug = Config.FLASK_ENV != 'production'
    app.run(debug=debug, port=5000)
