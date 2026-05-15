# # import threading #runs audio & face detection
# # import time
# # import os
# # import queue

# # from audio.audio import start_audio_monitoring
# # from Face.face  import start_face_detection
# # from app import app

# # EVIDENCE_DIR = os.path.abspath("evidence")

# # def run_flask():
# #     app.run(host="0.0.0.0", port=5000, debug=False,threaded=True)

# # def run_proctoring_system():
# #     print("Proctoring System - Starting...")
# #     os.makedirs(EVIDENCE_DIR, exist_ok=True)
# #     flask_thread = threading.Thread(target=run_flask, daemon=True, name="Flask")
# #     flask_thread.start()

# #     stop_event  = threading.Event()
# #     event_queue = queue.Queue(maxsize=50)

# #     audio_thread = threading.Thread(
# #         target=run_audio_thread,
# #         args=(stop_event, event_queue),
# #         daemon=True,
# #         name="AudioMonitor",
# #     )
# #     audio_thread.start()

# #     time.sleep(0.3)

# #     try:
# #         start_face_detection(
# #             stop_event=stop_event,
# #             evidence_dir=EVIDENCE_DIR,
# #             event_queue=event_queue,
# #         )
# #     except Exception as exc:
# #         print(f" Face detection error: {exc}")
# #     finally:
# #         stop_event.set()
# #         audio_thread.join(timeout=2)
# #         print("\n  Proctoring session ended.")


# # def run_audio_thread(stop_event: threading.Event, event_queue: queue.Queue):
# # #audio function runs in a seperate thread 
# #     def on_talking_detected(event: dict): #called automatically when speech is detected
# #         try:
# #             event_queue.put_nowait(event)
# #         except queue.Full:
# #             pass

# #         try:
# #             log_path = "evidence/audio_log.txt"
# #             with open(log_path, "a", encoding="utf-8") as f:
# #                 ts = event.get("timestamp", time.time())
# #                 f.write(f"{time.ctime(ts)} - talking_detected\n")
# #         except Exception as exc:
# #             print(f"  Audio log write failed: {exc}")

# #     try:
# #         print("  Starting audio monitoring thread …")
# #         start_audio_monitoring(
# #             stop_event=stop_event,
# #             on_talking_detected=on_talking_detected,
# #         )
# #     except Exception as exc:
# #         print(f"  Audio thread error: {exc}")


# # def run_proctoring_system() :
# # #Audio will run in bg thread and face in main thread
# #     print("Proctoring System — Starting....")


# #     os.makedirs(EVIDENCE_DIR, exist_ok=True)

# #     stop_event  = threading.Event()
# #     event_queue = queue.Queue(maxsize=50)  

# #     audio_thread = threading.Thread(
# #         target=run_audio_thread,
# #         args=(stop_event, event_queue),
# #         daemon=True,          # exits automatically when main thread ends
# #         name="AudioMonitor",
# #     )
# #     audio_thread.start()

# #     time.sleep(0.3) #kept a delay for 0.3 sec after before face strts

# #     try:
# #         start_face_detection(
# #             stop_event=stop_event,
# #             evidence_dir=EVIDENCE_DIR,
# #             event_queue=event_queue,
# #         )
# #     except Exception as exc:
# #         print(f" Face detection error: {exc}")
# #     finally:
# #         stop_event.set()
# #         audio_thread.join(timeout=2)
# #         print("\n  Proctoring session ended.")

# # if __name__ == "__main__":
# #     run_proctoring_system()


# import threading
# import time
# import os
# import queue

# from audio.audio import start_audio_monitoring
# from Face.face   import start_face_detection
# from app         import app          # Flask app object

# EVIDENCE_DIR = os.path.abspath("evidence")


# def run_flask():
#     """
#     Runs Flask in a background thread.

#     WHY use_reloader=False:
#         Flask's default reloader spawns a second process to watch
#         for file changes. That second process does NOT share memory
#         with the main process, so shared.output_frame would always
#         be None in it. Turning reloader off keeps everything in one
#         single process → shared memory works correctly.

#     WHY threaded=True:
#         Allows Flask to handle multiple browser connections at once
#         (e.g. /video_feed + page load) without blocking each other.
#     """
#     print("  Flask starting on http://127.0.0.1:5000 …")
#     app.run(
#         host="0.0.0.0",
#         port=5000,
#         debug=False,        # must be False — debug=True forks a second process
#         threaded=True,
#         use_reloader=False  # must be False — same reason as above
#     )


# def run_audio_thread(stop_event: threading.Event, event_queue: queue.Queue):
#     def on_talking_detected(event: dict):
#         try:
#             event_queue.put_nowait(event)
#         except queue.Full:
#             pass
#         try:
#             with open("evidence/audio_log.txt", "a", encoding="utf-8") as f:
#                 ts = event.get("timestamp", time.time())
#                 f.write(f"{time.ctime(ts)} - talking_detected\n")
#         except Exception as exc:
#             print(f"  Audio log write failed: {exc}")

#     try:
#         print("  Starting audio monitoring thread …")
#         start_audio_monitoring(
#             stop_event=stop_event,
#             on_talking_detected=on_talking_detected,
#         )
#     except Exception as exc:
#         print(f"  Audio thread error: {exc}")


# def run_proctoring_system():
#     print("Proctoring System — Starting …")
#     os.makedirs(EVIDENCE_DIR, exist_ok=True)

#     # ── 1. Start Flask FIRST (background thread) ──────────────
#     # Flask must be running before face.py begins so the browser
#     # can connect and start receiving frames as soon as they appear.
#     flask_thread = threading.Thread(
#         target=run_flask,
#         daemon=True,
#         name="Flask"
#     )
#     flask_thread.start()
#     time.sleep(0.5)   # give Flask a moment to bind to port 5000
#     # ─────────────────────────────────────────────────────────

#     stop_event  = threading.Event()
#     event_queue = queue.Queue(maxsize=50)

#     # ── 2. Start audio (background thread) ───────────────────
#     audio_thread = threading.Thread(
#         target=run_audio_thread,
#         args=(stop_event, event_queue),
#         daemon=True,
#         name="AudioMonitor",
#     )
#     audio_thread.start()
#     # ─────────────────────────────────────────────────────────

#     time.sleep(0.3)

#     # ── 3. Start face detection (MAIN thread — blocking) ──────
#     # face.py runs in the main thread because OpenCV's imshow/
#     # waitKey must run on the main thread on Windows.
#     # It writes frames into shared.output_frame every loop.
#     # Flask (running in its background thread) reads from there.
#     try:
#         start_face_detection(
#             stop_event=stop_event,
#             evidence_dir=EVIDENCE_DIR,
#             event_queue=event_queue,
#         )
#     except Exception as exc:
#         print(f"  Face detection error: {exc}")
#     finally:
#         stop_event.set()
#         audio_thread.join(timeout=2)
#         print("\n  Proctoring session ended.")


# if __name__ == "__main__":
#     run_proctoring_system()

from flask import Flask, render_template, request, redirect, session
import sqlite3

app=Flask(__name__)
app.secret_key='secret123'

@app.route('/')
def home():
    return render_template('login.html')

# REGISTER USER
@app.route('/register', methods=['POST'])
def register():

    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO users (username,email,password)
    VALUES (?,?,?)
    ''', (username,email,password))

    conn.commit()
    conn.close()

    return redirect('/start_exam')

# START EXAM
@app.route('/start_exam')
def start_exam():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id FROM questions
    ORDER BY RANDOM()
    ''')

    question_ids = [row[0] for row in cursor.fetchall()]

    session['question_order'] = question_ids
    session['current_question'] = 0

    # palette status
    status = {}

    for qid in question_ids:
        status[str(qid)] = 'not-visited'

    session['status'] = status

    conn.close()

    return redirect('/exam')

# EXAM PAGE
@app.route('/exam')
def exam():

    current_index = session['current_question']

    question_id = session['question_order'][current_index]

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT * FROM questions
    WHERE id=?
    ''', (question_id,))

    question = cursor.fetchone()

    conn.close()

    # update status when visited
    status = session['status']

    if status[str(question_id)] == 'not-visited':
        status[str(question_id)] = 'not-answered'

    session['status'] = status

    return render_template(
        'exam.html',
        question=question,
        qno=current_index + 1,
        total=len(session['question_order']),
        order=session['question_order'],
        status=status
    )


# SAVE ANSWER
@app.route('/save_answer', methods=['POST'])
def save_answer():

    answer = request.form.get('answer')
    action = request.form.get('action')

    current_index = session['current_question']

    question_id = session['question_order'][current_index]

    status = session['status']

    if answer:
        status[str(question_id)] = 'answered'

    if action == 'review':
        status[str(question_id)] = 'review'

    session['status'] = status

    session['current_question'] += 1

    if session['current_question'] >= len(session['question_order']):
        return 'Exam Finished Successfully'

    return redirect('/exam')


# OPEN QUESTION FROM PALETTE
@app.route('/goto/<int:index>')
def goto(index):

    session['current_question'] = index

    return redirect('/exam')


# ADMIN PAGE
@app.route('/admin')
def admin():

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')

    total_users = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'admin.html',
        total_users=total_users
    )


if __name__ == '__main__':
    app.run(debug=True)