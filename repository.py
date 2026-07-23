"""Repository layer.

All SQL queries used by the application live here. No business logic or
HTTP-related code should appear in this module.
"""

from typing import Any

from database import get_db


class TaskRepository:
    """Encapsulates raw SQL access to the tasks table."""

    def list_tasks(
        self, search: str | None = None, done: bool | None = None
    ) -> list[dict[str, Any]]:
        """Return tasks optionally filtered by title search and completion state."""
        query = "SELECT id, title, done, created_at, updated_at FROM tasks WHERE 1=1"
        params: list[Any] = []

        if search is not None:
            query += " AND title ILIKE %s"
            params.append(f"%{search}%")

        if done is not None:
            query += " AND done = %s"
            params.append(done)

        query += " ORDER BY id ASC"

        with get_db() as connection:
            cursor = connection.execute(query, params)
            return cursor.fetchall()

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        """Return a single task by id, or None if it does not exist."""
        query = (
            "SELECT id, title, done, created_at, updated_at "
            "FROM tasks WHERE id = %s"
        )
        with get_db() as connection:
            cursor = connection.execute(query, (task_id,))
            return cursor.fetchone()

    def create_task(self, title: str, done: bool) -> dict[str, Any]:
        """Insert a new task and return the created row."""
        query = (
            "INSERT INTO tasks (title, done) VALUES (%s, %s) "
            "RETURNING id, title, done, created_at, updated_at"
        )
        with get_db() as connection:
            cursor = connection.execute(query, (title, done))
            return cursor.fetchone()

    def update_task(
        self, task_id: int, title: str, done: bool
    ) -> dict[str, Any] | None:
        """Update an existing task and return the updated row, or None if missing."""
        query = (
            "UPDATE tasks SET title = %s, done = %s, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = %s "
            "RETURNING id, title, done, created_at, updated_at"
        )
        with get_db() as connection:
            cursor = connection.execute(query, (title, done, task_id))
            return cursor.fetchone()

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by id. Returns True if a row was deleted."""
        query = "DELETE FROM tasks WHERE id = %s"
        with get_db() as connection:
            cursor = connection.execute(query, (task_id,))
            return cursor.rowcount > 0

    def get_stats(self) -> dict[str, int]:
        """Return aggregate counts of total, completed, and pending tasks."""
        query = (
            "SELECT "
            "COUNT(*) AS total_tasks, "
            "COUNT(*) FILTER (WHERE done = TRUE) AS completed_tasks, "
            "COUNT(*) FILTER (WHERE done = FALSE) AS pending_tasks "
            "FROM tasks"
        )
        with get_db() as connection:
            cursor = connection.execute(query)
            return cursor.fetchone()


task_repository = TaskRepository()