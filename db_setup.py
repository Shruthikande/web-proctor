import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# USERS TABLE
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT,
    password TEXT
)
''')

# QUESTIONS TABLE
cursor.execute('''
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    question TEXT,
    option1 TEXT,
    option2 TEXT,
    option3 TEXT,
    option4 TEXT,
    correct_answer TEXT
)
''')

# SAMPLE QUESTIONS
sample_questions = [
    (
        'IT',
        'What does CPU stand for?',
        'Central Processing Unit',
        'Computer Processing Unit',
        'Central Program Unit',
        'Control Processing Unit',
        'Central Processing Unit'
    ),
    (
        'IT',
        'Which language is used for web apps?',
        'Python',
        'JavaScript',
        'HTML',
        'All of these',
        'All of these'
    ),
    (
        'IT',
        'What is RAM?',
        'Storage Device',
        'Memory',
        'CPU',
        'Software',
        'Memory'
    )
]

cursor.executemany('''
INSERT INTO questions
(subject,question,option1,option2,option3,option4,correct_answer)
VALUES (?,?,?,?,?,?,?)
''', sample_questions)

conn.commit()
conn.close()

print('Database created successfully')