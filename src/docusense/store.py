"""SQLite persistence: question bank + quiz attempts."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from .schemas import MCQ

DEFAULT_DB = Path("data") / "docusense.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    page INTEGER NOT NULL,
    number INTEGER NOT NULL,
    stem TEXT NOT NULL,
    options TEXT NOT NULL,
    answer TEXT,
    explanation TEXT,
    issues TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    source TEXT NOT NULL,
    topic TEXT,
    selected TEXT NOT NULL,
    correct TEXT,
    is_correct INTEGER,
    ts REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        with closing(self._conn()) as c:
            c.executescript(_SCHEMA)
            c.commit()

    def _conn(self) -> sqlite3.Connection:
        if self._memory is not None:
            return _Keep(self._memory)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- question bank ------------------------------------------------------
    def replace_questions(self, source: str, mcqs: list[MCQ]) -> None:
        with closing(self._conn()) as c:
            c.execute("DELETE FROM questions WHERE source = ?", (source,))
            c.executemany(
                "INSERT OR REPLACE INTO questions VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (q.id, q.source, q.page, q.number, q.stem, json.dumps(q.options),
                     q.answer, q.explanation, json.dumps(q.issues))
                    for q in mcqs
                ],
            )
            c.commit()

    def delete_source(self, source: str) -> None:
        with closing(self._conn()) as c:
            c.execute("DELETE FROM questions WHERE source = ?", (source,))
            c.commit()

    def load_questions(self, sources: list[str] | None = None) -> list[MCQ]:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT * FROM questions ORDER BY source, number").fetchall()
        mcqs = [
            MCQ(r["id"], r["source"], r["page"], r["number"], r["stem"],
                json.loads(r["options"]), r["answer"], r["explanation"],
                json.loads(r["issues"]))
            for r in rows
        ]
        return [q for q in mcqs if sources is None or q.source in sources]

    # -- attempts -----------------------------------------------------------
    def record_attempt(self, q: MCQ, selected: str, topic: str | None = None) -> None:
        is_correct = None if q.answer is None else int(selected == q.answer)
        with closing(self._conn()) as c:
            c.execute(
                "INSERT INTO attempts (question_id, source, topic, selected, correct, is_correct, ts)"
                " VALUES (?,?,?,?,?,?,?)",
                (q.id, q.source, topic, selected, q.answer, is_correct, time.time()),
            )
            c.commit()

    def accuracy_by(self, column: str) -> list[dict]:
        """Accuracy grouped by 'source' or 'topic'. Unscorable attempts are excluded."""
        if column not in ("source", "topic"):
            raise ValueError(column)
        with closing(self._conn()) as c:
            rows = c.execute(
                f"SELECT {column} AS name, COUNT(*) AS n, SUM(is_correct) AS right "
                f"FROM attempts WHERE is_correct IS NOT NULL AND {column} IS NOT NULL "
                f"GROUP BY {column}"
            ).fetchall()
        out = [
            {"name": r["name"], "attempts": r["n"], "correct": r["right"],
             "accuracy": round(100 * r["right"] / r["n"], 1)}
            for r in rows
        ]
        return sorted(out, key=lambda d: d["accuracy"])

    def overall(self) -> dict:
        with closing(self._conn()) as c:
            r = c.execute(
                "SELECT COUNT(*) AS n, SUM(is_correct) AS right FROM attempts "
                "WHERE is_correct IS NOT NULL"
            ).fetchone()
        n, right = r["n"], r["right"] or 0
        return {"attempts": n, "correct": right,
                "accuracy": round(100 * right / n, 1) if n else None}

    def wrong_questions(self) -> list[dict]:
        """Questions whose most recent scorable attempt was wrong."""
        with closing(self._conn()) as c:
            rows = c.execute(
                "SELECT q.*, a.selected AS picked FROM attempts a "
                "JOIN questions q ON q.id = a.question_id "
                "WHERE a.id IN (SELECT MAX(id) FROM attempts WHERE is_correct IS NOT NULL "
                "               GROUP BY question_id) AND a.is_correct = 0"
            ).fetchall()
        return [
            {"source": r["source"], "page": r["page"], "number": r["number"],
             "stem": r["stem"], "options": json.loads(r["options"]),
             "picked": r["picked"], "answer": r["answer"],
             "explanation": r["explanation"]}
            for r in rows
        ]


class _Keep:
    """Wrap a shared in-memory connection so closing() doesn't destroy it."""
    def __init__(self, conn: sqlite3.Connection):
        self._c = conn
        conn.row_factory = sqlite3.Row

    def __getattr__(self, name):
        return getattr(self._c, name)

    def close(self):
        pass
