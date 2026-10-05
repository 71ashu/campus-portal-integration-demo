"""
Campus student portal (the LTI "platform") for the integration demo.

Plays the role Canvas, Blackboard, or a university's own portal plays in a
real deployment: it owns the student's sign-in, and it launches third-party
tools — here the AI Course Advisor — inside an iframe by signing a
short-lived launch token that the tool verifies against this portal's
published public key.

The portal never sees grades or course history. Those flow directly from the
SIS to the advisor.
"""
import hashlib
import json
import os
import time
import uuid
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import load_dotenv
from flask import (
    Flask, abort, jsonify, make_response, redirect, render_template, request, session, url_for,
)

load_dotenv()

BASE_DIR = Path(__file__).parent

PORTAL_URL = os.getenv("PORTAL_URL", "http://127.0.0.1:5100").rstrip("/")
ADVISOR_LAUNCH_URL = os.getenv("ADVISOR_LAUNCH_URL", "http://localhost:5000/lti/launch")
ADVISOR_APP_ORIGIN = os.getenv("ADVISOR_APP_ORIGIN", "http://localhost:5173").rstrip("/")
ADVISOR_CLIENT_ID = os.getenv("ADVISOR_CLIENT_ID", "scu-portal")
DEPLOYMENT_ID = os.getenv("ADVISOR_DEPLOYMENT_ID", "scu-1")
LAUNCH_TOKEN_SECONDS = 60

LTI_CLAIM = "https://purl.imsglobal.org/spec/lti/claim/"
LEARNER_ROLE = "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-portal-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_NAME="portal_session",
)


# --------------------------------------------------------------------------
# Signing key + JWKS
# --------------------------------------------------------------------------

def _load_private_key():
    """PORTAL_PRIVATE_KEY (PEM) in production; locally, a key generated once
    and kept in keys/ (gitignored) so launches survive restarts."""
    pem = os.getenv("PORTAL_PRIVATE_KEY", "").replace("\\n", "\n").encode()
    if not pem:
        key_path = BASE_DIR / "keys" / "portal_private.pem"
        if not key_path.exists():
            key_path.parent.mkdir(exist_ok=True)
            generated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            key_path.write_bytes(generated.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            key_path.chmod(0o600)
        pem = key_path.read_bytes()
    return serialization.load_pem_private_key(pem, password=None)


PRIVATE_KEY = _load_private_key()
_public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(PRIVATE_KEY.public_key(), as_dict=True)
# Key ID = thumbprint of the public key, so a rotated key gets a new kid.
KEY_ID = hashlib.sha256(json.dumps(
    {k: _public_jwk[k] for k in ("e", "kty", "n")}, sort_keys=True, separators=(",", ":"),
).encode()).hexdigest()[:16]
PUBLIC_JWK = {**_public_jwk, "kid": KEY_ID, "use": "sig", "alg": "RS256"}


@app.route("/.well-known/jwks.json")
def jwks():
    resp = jsonify({"keys": [PUBLIC_JWK]})
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# --------------------------------------------------------------------------
# Directory + mock SSO
# --------------------------------------------------------------------------

USERS = {u["sisId"]: u for u in json.loads((BASE_DIR / "users.json").read_text())}


def current_user():
    return USERS.get(session.get("sis_id"))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.after_request
def _security_headers(resp):
    # Only the launch page is meant to be framed (by our own shell).
    if "Content-Security-Policy" not in resp.headers:
        resp.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    resp.headers.setdefault("Referrer-Policy", "strict-origin")
    return resp


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("course_planning" if current_user() else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Stand-in for campus SSO (Shibboleth / Okta / Entra ID). The portal is
    the only thing a student ever signs into; tools get a signed launch."""
    error = None
    if request.method == "POST":
        sis_id = (request.form.get("sisId") or "").strip().upper()
        if sis_id in USERS:
            session.clear()
            session["sis_id"] = sis_id
            return redirect(url_for("course_planning"))
        error = "No student with that University ID."
    return render_template("login.html", users=USERS.values(), error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Portal pages
# --------------------------------------------------------------------------

@app.route("/course-planning")
@login_required
def course_planning():
    advisor_backend = urlsplit(ADVISOR_LAUNCH_URL)
    return render_template(
        "course_planning.html",
        user=current_user(),
        # Messages may come from the advisor SPA or from the advisor's own
        # launch error page, which is served by its API host.
        advisor_origins=[ADVISOR_APP_ORIGIN, f"{advisor_backend.scheme}://{advisor_backend.netloc}"],
    )


# --------------------------------------------------------------------------
# Tool launch
# --------------------------------------------------------------------------

def _launch_token(user):
    now = int(time.time())
    claims = {
        "iss": PORTAL_URL,
        "aud": ADVISOR_CLIENT_ID,
        # Opaque, stable per student; the SIS ID travels in the LIS claim.
        "sub": hashlib.sha256(f"{PORTAL_URL}|{user['sisId']}".encode()).hexdigest()[:32],
        "iat": now,
        "exp": now + LAUNCH_TOKEN_SECONDS,
        "nonce": uuid.uuid4().hex,
        "jti": uuid.uuid4().hex,
        "name": user["name"],
        LTI_CLAIM + "message_type": "LtiResourceLinkRequest",
        LTI_CLAIM + "version": "1.3.0",
        LTI_CLAIM + "deployment_id": DEPLOYMENT_ID,
        LTI_CLAIM + "target_link_uri": ADVISOR_LAUNCH_URL,
        LTI_CLAIM + "resource_link": {"id": "course-planning"},
        LTI_CLAIM + "roles": [LEARNER_ROLE],
        LTI_CLAIM + "lis": {"person_sourcedid": user["sisId"]},
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": KEY_ID})


@app.route("/launch/advisor")
def launch_advisor():
    """Loaded inside the Course Planning iframe. Returns a self-submitting
    form that POSTs a freshly signed launch token to the advisor, so the
    token never touches the portal's JavaScript or a URL."""
    user = current_user()
    if not user:
        abort(401)
    resp = make_response(render_template(
        "launch.html", launch_url=ADVISOR_LAUNCH_URL, id_token=_launch_token(user),
    ))
    resp.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=int(os.getenv("PORT", "5100")))
