from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(os.environ.get("SQLITE_LAB_DB", Path(__file__).with_name("lab.sqlite3")))


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'dropped')),
    grade REAL CHECK (grade IS NULL OR (grade >= 0 AND grade <= 100)),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (student_id, course_id)
);
"""


SEED_SQL = """
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO students (id, name, cohort, email, score) VALUES
    (1, 'An Nguyen', 'A1', 'an.nguyen@example.edu', 91.5),
    (2, 'Binh Tran', 'A1', 'binh.tran@example.edu', 84.0),
    (3, 'Chi Le', 'B2', 'chi.le@example.edu', 77.5),
    (4, 'Dung Pham', 'B2', 'dung.pham@example.edu', 88.0),
    (5, 'Hanh Vo', 'C3', 'hanh.vo@example.edu', 95.0);

INSERT OR IGNORE INTO courses (id, code, title, credits) VALUES
    (1, 'DSA101', 'Data Structures and Algorithms', 4),
    (2, 'DB201', 'Database Systems', 3),
    (3, 'AI301', 'Applied AI Systems', 3);

INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, grade) VALUES
    (1, 1, 1, 'completed', 92.0),
    (2, 1, 2, 'active', NULL),
    (3, 2, 1, 'completed', 86.0),
    (4, 3, 2, 'completed', 79.0),
    (5, 4, 3, 'active', NULL),
    (6, 5, 1, 'completed', 96.0),
    (7, 5, 3, 'active', NULL);
"""


def create_database(db_path: str | Path | None = None, *, reset: bool = False) -> Path:
    """Create a repeatable SQLite database and return its path."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if reset and path.exists():
        path.unlink()

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()

    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the SQLite lab database.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--reset", action="store_true", help="Delete the existing database before seeding.")
    args = parser.parse_args()

    db_path = create_database(args.db, reset=args.reset)
    print(f"Database ready: {db_path}")


if __name__ == "__main__":
    main()
