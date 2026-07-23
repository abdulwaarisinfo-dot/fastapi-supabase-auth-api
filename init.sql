-- Creates the tasks table if it does not already exist and seeds three
-- example tasks, but only the first time the table is empty.

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF (SELECT COUNT(*) FROM tasks) = 0 THEN
        INSERT INTO tasks (title, done) VALUES
            ('Buy milk', FALSE),
            ('Read a book', FALSE),
            ('Write FastAPI project', TRUE);
    END IF;
END $$;