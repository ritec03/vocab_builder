-- schema.sql

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    pos TEXT NOT NULL,
    freq INTEGER NOT NULL,
    UNIQUE (word, pos)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    user_name TEXT NOT NULL,
    UNIQUE (user_name)
);

CREATE TABLE IF NOT EXISTS learning_data (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    score INTEGER CHECK (score >= 0 AND score <= 10) NOT NULL,
    UNIQUE (user_id, word_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY,
    task_type TEXT NOT NULL,
    template TEXT NOT NULL,
    description TEXT NOT NULL,
    examples TEXT NOT NULL, -- examples of template usage, store as a json string
    starting_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
    UNIQUE (template)
);

CREATE TABLE IF NOT EXISTS template_parameters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    UNIQUE (template_id, name), -- Unique constraint for template_id and name combination
    FOREIGN KEY (template_id) REFERENCES templates(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    template_id INTEGER NOT NULL,
    answer TEXT,
    FOREIGN KEY (template_id) REFERENCES templates(id)
);

CREATE TABLE IF NOT EXISTS task_target_words (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY,
    resource_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_resources (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    parameter_id INTEGER NOT NULL,
    UNIQUE (task_id, parameter_id), -- cant have same two resources for same parameter
    FOREIGN KEY (parameter_id) REFERENCES template_parameters(id),
    -- TODO add constraint not to include parameters that are not parameters for that template
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (resource_id) REFERENCES resources(id)
);

CREATE TABLE IF NOT EXISTS resource_words (
    resource_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    UNIQUE (resource_id, word_id), -- each word appears in a resource once only
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS user_lessons (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY,
    lesson_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    FOREIGN KEY (lesson_id) REFERENCES user_lessons(id),
    UNIQUE (lesson_id, sequence_number)  -- Ensures sequence numbers are unique within each lesson
);

CREATE TABLE IF NOT EXISTS history_entries (
    id INTEGER PRIMARY KEY,
    evaluation_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    response TEXT,
    FOREIGN KEY (evaluation_id) REFERENCES evaluations(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    UNIQUE (evaluation_id, sequence_number)  -- Ensures sequence numbers are unique within each evaluation
);

CREATE TABLE IF NOT EXISTS entry_scores (
    id INTEGER PRIMARY KEY,
    history_entry_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    score INTEGER CHECK (score >= 0 AND score <= 10) NOT NULL,
    FOREIGN KEY (history_entry_id) REFERENCES history_entries(id),
    FOREIGN KEY (word_id) REFERENCES words(id),
    UNIQUE (history_entry_id, word_id)  -- Ensuring one score per word per history entry
);