
│
├── app/                         # Main application (Flask backend)
│   ├── __init__.py
│   ├── routes.py                # API routes (start exam, alerts, etc.)
│   ├── config.py                # Config (paths, thresholds)
│
├── modules/                     # All AI modules (core logic)
│   ├── face/
│   │   ├── face_detector.py     # MediaPipe / OpenCV face detection
│   │   ├── face_verify.py       # DeepFace identity verification
│   │
│   ├── gaze/
│   │   ├── gaze_tracker.py      # Eye / head direction logic
│   │
│   ├── hand/
│   │   ├── hand_detector.py     # MediaPipe hands
│   │
│   ├── object/
│   │   ├── yolo_detector.py     # YOLO object detection
│   │
│   ├── audio/
│   │   ├── audio_monitor.py     # sounddevice + webrtcvad
│
├── services/                    # Decision-making logic
│   ├── decision_engine.py       # Combine all outputs
│   ├── alert_service.py         # Handle warnings, termination
│   ├── recording_service.py     # Record video evidence
│
├── models/                      # Model files
│   ├── yolo/                    # YOLO weights
│   ├── face/                    # (optional embeddings storage)
│
├── storage/                     # Saved data
│   ├── embeddings/              # Registered face embeddings
│   ├── videos/                  # Recorded cheating clips
│   ├── logs/                    # Event logs
│
├── utils/                       # Helper functions
│   ├── video_utils.py
│   ├── audio_utils.py
│   ├── config_utils.py
│
├── static/                      # Frontend static files
│   ├── js/
│   ├── css/
│
├── templates/                   # HTML (Flask frontend)
│   ├── index.html
│   ├── exam.html
│
├── main.py                      # Entry point (run server)
├── requirements.txt             # Dependencies
└── README.md