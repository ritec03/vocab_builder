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
    name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    template TEXT NOT NULL,
    description TEXT NOT NULL,
    examples TEXT NOT NULL, -- examples of template usage
    UNIQUE (name),
    UNIQUE (template)
);

CREATE TABLE IF NOT EXISTS template_parameters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    UNIQUE (template_id, name), -- Unique constraint for template_id and name combination
    FOREIGN KEY (template_id) REFERENCES template(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    template_id INTEGER NOT NULL,
    description TEXT,
    FOREIGN KEY (template_id) REFERENCES templates(id)
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

CREATE TABLE IF NOT EXISTS user_lesson_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    evaluation_json TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
