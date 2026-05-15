from flask import (Flask, render_template, request, redirect,
                url_for, session, Response, jsonify)
import cv2, time, threading, queue, os, random
from datetime import datetime
import shared
from Database.db import get_db_connection
from functools import wraps

app = Flask(__name__)
app.secret_key = "nielit_proctor_secret_2024"

# Evidence is stored inside static/ so Flask can serve the images directly
# via url_for('static', filename='evidence/...') in the admin dashboard.
EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "evidence")
_proctoring_started = False
_proctor_lock       = threading.Lock()

# ── DECORATORS ────────────────────────────────────────────────

def login_required(f):
    """Redirect to login if the student is not in session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Redirect if not logged in as admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ── REGISTER ─────────────────────────────────────────────────

from routes.auth_routes import register
app.add_url_rule("/register",      "register",      register, methods=["GET","POST"])
app.add_url_rule("/register-page", "register_page", register, methods=["GET","POST"])

# ── MJPEG STREAM ──────────────────────────────────────────────

def generate_frames():
    import numpy as np
    while True:
        with shared.frame_lock:
            frame = shared.output_frame
        if frame is None:
            blank = 128 * np.ones((200, 280, 3), dtype="uint8")
            cv2.putText(blank, "Waiting for exam start...",
                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)
            ok, buf = cv2.imencode(".jpg", blank)
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            time.sleep(0.1)
            continue
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# ── VIOLATION HELPERS ─────────────────────────────────────────

def _save_violation(student_id, v_type):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO violations (student_id, violation_type, timestamp) VALUES (?,?,?)",
        (student_id, v_type, ts)
    )
    conn.commit()
    conn.close()

VIOLATION_MESSAGES = {
    "tab_switch":       "Tab switch Detected",
    "window_blur":      "Student left exam window",
    "fullscreen_exit":  "Fullscreen exited",
    "multiple_person":  "Multiple persons detected",
    "mobile_phone":     "Mobile phone detected",
    "talking_detected": "Voice detected",
    "no_face":          "No face detected",
    "face_mismatch":    "Face identity mismatch",
    "gaze_away":        "Looking away the screen",
    "laptop":           "Laptop detected",
    "book":             "Book detected",
}

# ── WARNING POLLING ───────────────────────────────────────────

@app.route("/get-warnings")
def get_warnings():
    with shared.warning_lock:
        count    = shared.warning_count
        messages = shared.warning_messages.copy()
        shared.warning_messages.clear()
    return jsonify({"count": count, "messages": messages})

# ── LOG VIOLATION (from browser JS) ──────────────────────────

@app.route("/log-violation", methods=["POST"])
def log_violation():
    data       = request.get_json()
    v_type     = data.get("type", "unknown")
    student_id = session.get("user_id")
    ts         = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if student_id:
        _save_violation(student_id, v_type)

    msg = VIOLATION_MESSAGES.get(v_type, v_type)

    with shared.warning_lock:
        shared.warning_count += 1
        count = shared.warning_count
        shared.warning_messages.append({
            "type": v_type, "message": msg,
            "count": count, "time": ts
        })

    print(f"  WARNING [{count}/15] — {msg}")
    return jsonify({"status": "logged", "total_warnings": count})

# ── PROCTORING THREADS ────────────────────────────────────────

def run_audio_thread(stop_event, event_queue):
    from audio.audio import start_audio_monitoring
    def on_talking(event):
        try:
            event_queue.put_nowait(event)
        except queue.Full:
            pass
        student_id = session.get("user_id")
        if student_id:
            _save_violation(student_id, "talking_detected")
    try:
        start_audio_monitoring(stop_event=stop_event,
                               on_talking_detected=on_talking)
    except Exception as e:
        print(f"  Audio thread error: {e}")

def run_face_thread(stop_event, event_queue):
    print("  FACE THREAD STARTED")
    try:
        from Face.face import start_face_detection
    except Exception as e:
        print(f"  Face import error: {e}")
        return
    try:
        start_face_detection(stop_event=stop_event,
                             evidence_dir=EVIDENCE_DIR,
                             event_queue=event_queue)
    except Exception as e:
        import traceback
        print(f"  Face runtime error: {e}")
        traceback.print_exc()

@app.route("/start-proctoring")
def start_proctoring():
    global _proctoring_started
    with _proctor_lock:
        if _proctoring_started:
            return jsonify({"status": "already_running"})
        _proctoring_started = True

    with shared.warning_lock:
        shared.warning_count    = 0
        shared.warning_messages = []

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    stop_event  = threading.Event()
    event_queue = queue.Queue(maxsize=50)
    app.config["stop_event"]  = stop_event
    app.config["event_queue"] = event_queue

    threading.Thread(target=run_audio_thread, args=(stop_event, event_queue),
                     daemon=True, name="AudioMonitor").start()
    threading.Thread(target=run_face_thread,  args=(stop_event, event_queue),
                     daemon=True, name="FaceDetection").start()

    print("  Proctoring started — face + audio running.")
    return jsonify({"status": "started"})

@app.route("/stop-proctoring")
def stop_proctoring():
    global _proctoring_started
    stop_event = app.config.get("stop_event")
    if stop_event:
        stop_event.set()
    with _proctor_lock:
        _proctoring_started = False
    with shared.frame_lock:
        shared.output_frame = None
    print("  Proctoring stopped.")
    return jsonify({"status": "stopped"})

# ── STUDENT PAGES ─────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("Login.html")

    email    = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    conn     = get_db_connection()
    user     = conn.execute(
        "SELECT * FROM students WHERE email=? AND password=?",
        (email, password)
    ).fetchone()

    if user:
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        # log the login event
        conn.execute(
            "INSERT INTO login_logs (student_id) VALUES (?)", (user["id"],)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("Login.html", error="Invalid email or password.")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html",
                           user_name=session.get("user_name","Student"))

@app.route("/instructions")
@login_required
def instructions():
    quiz = request.args.get("quiz", "it")
    return render_template("Instructions.html", quiz=quiz)

@app.route("/system-check")
@login_required
def system_check():
    quiz = request.args.get("quiz", "it")
    return render_template("system_check.html", quiz=quiz)

# ── QUIZ ROUTES (fetch + shuffle questions) ───────────────────

def _get_shuffled_questions(subject, student_id):
    """Fetch all questions for a subject and shuffle them consistently per student."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM questions WHERE subject=?", (subject,)
    ).fetchall()
    conn.close()

    questions = [dict(r) for r in rows]

    # Seed with student_id so the order is the same if they refresh,
    # but different from every other student.
    rng = random.Random(student_id)
    rng.shuffle(questions)

    # Also shuffle the options within each question so A is not always correct
    for q in questions:
        opts = [
            ("A", q["option_a"]),
            ("B", q["option_b"]),
            ("C", q["option_c"]),
            ("D", q["option_d"]),
        ]
        original_correct_text = {
            "A": q["option_a"], "B": q["option_b"],
            "C": q["option_c"], "D": q["option_d"],
        }[q["correct_answer"]]

        rng.shuffle(opts)
        q["option_a"], q["option_b"], q["option_c"], q["option_d"] = \
            opts[0][1], opts[1][1], opts[2][1], opts[3][1]

        # Update correct_answer to new letter after shuffle
        for new_letter, (orig_letter, text) in enumerate(opts):
            if text == original_correct_text:
                q["correct_answer"] = ["A","B","C","D"][new_letter]
                break

    return questions

@app.route("/it-quiz")
@login_required
def it_quiz():
    student_id = session["user_id"]

    # Block if student has already attempted Electronics
    conn = get_db_connection()
    already_attempted = conn.execute(
        "SELECT id FROM exam_attempts WHERE student_id=? AND subject=? AND submitted_at IS NOT NULL",
        (student_id, "Electronics")
    ).fetchone()
    if already_attempted:
        conn.close()
        return render_template("dashboard.html",
                               user_name=session.get("user_name", "Student"),
                               error="You have already attempted the Electronics exam. "
                                     "You cannot attempt the IT exam.")

    questions = _get_shuffled_questions("IT", student_id)

    # Record exam attempt start
    attempt = conn.execute(
        "SELECT id FROM exam_attempts WHERE student_id=? AND subject=? AND submitted_at IS NULL",
        (student_id, "IT")
    ).fetchone()
    if not attempt:
        conn.execute(
            "INSERT INTO exam_attempts (student_id, subject, total) VALUES (?,?,?)",
            (student_id, "IT", len(questions))
        )
        conn.commit()
    conn.close()

    return render_template("quiz.html",
                           questions=questions,
                           subject="IT",
                           subject_display="IT Quiz",
                           total=len(questions))

@app.route("/electronics-quiz")
@login_required
def electronics_quiz():
    student_id = session["user_id"]

    # Block if student has already attempted IT
    conn = get_db_connection()
    already_attempted = conn.execute(
        "SELECT id FROM exam_attempts WHERE student_id=? AND subject=? AND submitted_at IS NOT NULL",
        (student_id, "IT")
    ).fetchone()
    if already_attempted:
        conn.close()
        return render_template("dashboard.html",
                               user_name=session.get("user_name", "Student"),
                               error="You have already attempted the IT exam. "
                                     "You cannot attempt the Electronics exam.")

    questions = _get_shuffled_questions("Electronics", student_id)

    attempt = conn.execute(
        "SELECT id FROM exam_attempts WHERE student_id=? AND subject=? AND submitted_at IS NULL",
        (student_id, "Electronics")
    ).fetchone()
    if not attempt:
        conn.execute(
            "INSERT INTO exam_attempts (student_id, subject, total) VALUES (?,?,?)",
            (student_id, "Electronics", len(questions))
        )
        conn.commit()
    conn.close()

    return render_template("quiz.html",
                        questions=questions,
                        subject="Electronics",
                        subject_display="Electronics Quiz",
                        total=len(questions))

# ── SUBMIT EXAM ───────────────────────────────────────────────

@app.route("/submit-exam", methods=["POST"])
@login_required
def submit_exam():
    data       = request.get_json()
    answers    = data.get("answers", {})   # { "question_id": "A", ... }
    subject    = data.get("subject", "")
    student_id = session["user_id"]

    # Score the answers
    conn  = get_db_connection()
    score = 0
    total = 0
    for qid_str, chosen in answers.items():
        row = conn.execute(
            "SELECT correct_answer FROM questions WHERE id=?", (int(qid_str),)
        ).fetchone()
        if row:
            total += 1
            if row["correct_answer"] == chosen:
                score += 1

    # Save result
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """UPDATE exam_attempts
           SET submitted_at=?, score=?, total=?
           WHERE student_id=? AND subject=? AND submitted_at IS NULL""",
        (ts, score, total, student_id, subject)
    )
    conn.commit()
    conn.close()

    session["last_score"]   = score
    session["last_total"]   = total
    session["last_subject"] = subject

    return jsonify({"status": "ok", "score": score, "total": total})

@app.route("/submit")
def submit():
    score   = session.pop("last_score",   None)
    total   = session.pop("last_total",   None)
    subject = session.pop("last_subject", "")
    return render_template("submit.html",
                        score=score, total=total, subject=subject)

# ── ADMIN LOGIN ───────────────────────────────────────────────

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "nielit@admin2024"

@app.route("/admin-login", methods=["GET","POST"])
def admin_login():
    if request.method == "GET":
        return render_template("Login.html")

    username = request.form.get("username","")
    password = request.form.get("password","")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["is_admin"] = True
        return redirect(url_for("admin_dashboard"))

    return render_template("Login.html", error="Invalid credentials.")

@app.route("/admin-logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("login"))

# ADMIN DASHBOARD 

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db_connection()

    # Summary counts
    total_registered = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_logins     = conn.execute("SELECT COUNT(*) FROM login_logs").fetchone()[0]
    unique_attempted = conn.execute(
        "SELECT COUNT(DISTINCT student_id) FROM exam_attempts WHERE submitted_at IS NOT NULL"
    ).fetchone()[0]
    total_violations = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]

    # Per-student stats
    students = conn.execute("""
        SELECT
            s.id,
            s.name,
            s.email,
            s.department,
            COUNT(DISTINCT ll.id)  AS login_count,
            COUNT(DISTINCT ea.id)  AS attempt_count,
            COUNT(DISTINCT v.id)   AS violation_count
        FROM students s
        LEFT JOIN login_logs  ll ON ll.student_id = s.id
        LEFT JOIN exam_attempts ea ON ea.student_id = s.id AND ea.submitted_at IS NOT NULL
        LEFT JOIN violations   v  ON v.student_id  = s.id
        GROUP BY s.id
        ORDER BY s.name
    """).fetchall()

    # Violations breakdown per student
    violations_raw = conn.execute("""
        SELECT
            s.name,
            s.email,
            v.violation_type,
            v.timestamp
        FROM violations v
        JOIN students s ON s.id = v.student_id
        ORDER BY s.name, v.timestamp DESC
    """).fetchall()

    # Group violations by student
    violations_by_student = {}
    for row in violations_raw:
        key = row["email"]
        if key not in violations_by_student:
            violations_by_student[key] = {
                "name": row["name"],
                "email": row["email"],
                "violations": []
            }
        violations_by_student[key]["violations"].append({
            "type": row["violation_type"],
            "time": row["timestamp"]
        })

    # Violation type distribution
    viol_distribution = conn.execute("""
        SELECT violation_type, COUNT(*) as cnt
        FROM violations
        GROUP BY violation_type
        ORDER BY cnt DESC
    """).fetchall()

    # Exam scores
    exam_results = conn.execute("""
        SELECT s.name, s.email, ea.subject, ea.score, ea.total, ea.submitted_at
        FROM exam_attempts ea
        JOIN students s ON s.id = ea.student_id
        WHERE ea.submitted_at IS NOT NULL
        ORDER BY ea.submitted_at DESC
    """).fetchall()

    conn.close()

    # ── EVIDENCE IMAGES ──────────────────────────────────────
    # Collect saved evidence screenshots and group them by category
    # so they display in the admin dashboard under the right tab.
    evidence_images = {"face": [], "audio": [], "object": []}
    face_tags   = {"no_face", "multiple_faces", "multiple_faces_persistent"}
    audio_tags  = {"talking"}
    object_tags = {"phone", "laptop", "bottle", "book", "other_person"}

    if os.path.isdir(EVIDENCE_DIR):
        for fname in sorted(os.listdir(EVIDENCE_DIR), reverse=True):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            tag = fname.split("_")[0]
            rel = "evidence/" + fname          # relative to static/
            if tag in face_tags:
                evidence_images["face"].append(rel)
            elif tag in audio_tags:
                evidence_images["audio"].append(rel)
            elif tag in object_tags:
                evidence_images["object"].append(rel)

    return render_template("admin_dashboard.html",
        total_logins       = total_logins,
        unique_attempted   = unique_attempted,
        total_violations   = total_violations,
        students           = students,
        violations_by_student = violations_by_student,
        viol_distribution  = viol_distribution,
        exam_results       = exam_results,
        evidence_images    = evidence_images,
        user_name          = "Admin",         
    total_registered   = total_registered,
    )

@app.route("/admin/clear-violations", methods=["POST"])
@admin_required
def clear_violations():
    conn = get_db_connection()
    conn.execute("DELETE FROM violations")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))

# ── RUN ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("  Flask starting on http://127.0.0.1:5000")
    print("  Admin panel → http://127.0.0.1:5000/admin-login")
    print("  Camera detection will start only when exam begins.")
    app.run(host="0.0.0.0", port=5000,
            debug=True, threaded=True, use_reloader=False)