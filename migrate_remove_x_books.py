"""One-time migration: remove books with title 'X' and update unknown_book_count.

Run from the project root:
    python migrate_remove_x_books.py

Or against a specific database:
    HOME_LIBRARY_DB=sqlite:////data/home_library.db python migrate_remove_x_books.py
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import os

DATABASE_URL = os.environ.get("HOME_LIBRARY_DB", "sqlite:///home_library.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def main() -> None:
    # Ensure the unknown_book_count column exists (in case migration hasn't run yet)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE scans ADD COLUMN unknown_book_count INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
            print("Added unknown_book_count column to scans.")
        except Exception:
            pass  # Already exists

    db = Session()
    try:
        rows = db.execute(
            text("SELECT id, scan_id, title, author FROM books")
        ).fetchall()

        to_delete: list[int] = []
        scan_extra_unknown: dict[int, int] = defaultdict(int)

        for book_id, scan_id, title, author in rows:
            is_x_title = title is not None and title.strip().upper() == "X"
            is_null = not title and not author
            if is_x_title or is_null:
                to_delete.append(book_id)
                scan_extra_unknown[scan_id] += 1

        if not to_delete:
            print("No books to remove.")
            return

        print(f"Found {len(to_delete)} book(s) to remove across {len(scan_extra_unknown)} scan(s):")
        for book_id in to_delete:
            row = db.execute(text("SELECT title, author, scan_id FROM books WHERE id = :id"), {"id": book_id}).fetchone()
            print(f"  Book #{book_id} — title={row.title!r} author={row.author!r} (scan {row.scan_id})")

        confirm = input("\nDelete these books and update scan counts? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

        # Delete books
        db.execute(
            text(f"DELETE FROM books WHERE id IN ({','.join(str(i) for i in to_delete)})")
        )

        # Increment unknown_book_count on affected scans
        for scan_id, count in scan_extra_unknown.items():
            db.execute(
                text("UPDATE scans SET unknown_book_count = unknown_book_count + :count WHERE id = :id"),
                {"count": count, "id": scan_id},
            )

        db.commit()
        print(f"Done. Removed {len(to_delete)} book(s) and updated {len(scan_extra_unknown)} scan(s).")

    finally:
        db.close()


if __name__ == "__main__":
    main()
