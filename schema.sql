-- schema.sql

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY,
    word TEXT,
    pos TEXT,
    freq INTEGER,
    UNIQUE (word, pos)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    user_name TEXT,
    UNIQUE (user_name)
);

CREATE TABLE IF NOT EXISTS learning_data (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    word_id INTEGER,
    score INTEGER CHECK (score >= 0 AND score <= 10),
    UNIQUE (user_id, word_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY,
    template TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    template_id INTEGER,
    description TEXT,
    FOREIGN KEY (template_id) REFERENCES templates(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY,
    resource_text TEXT
);

CREATE TABLE IF NOT EXISTS task_resources (
    id INTEGER PRIMARY KEY,
    task_id INTEGER,
    resource_id INTEGER,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (resource_id) REFERENCES resources(id)
);

CREATE TABLE IF NOT EXISTS resource_words (
    resource_id INTEGER,
    word_id INTEGER,
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS user_lesson_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    evaluation_json TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
