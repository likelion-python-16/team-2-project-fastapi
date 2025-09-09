"""
Backfill script: migrate legacy plain `users.phone` to encrypted storage.

Usage:
  PYTHONPATH=. python scripts/migrate_encrypt_phones.py

It will:
  - For users with phone_encrypted is NULL and phone is NOT NULL:
      call User.set_phone(phone) to encrypt + fingerprint and clear plain.
  - For users with both phone_encrypted and phone set:
      clear the plain phone column.
"""

from app.core.database import SessionLocal
from app.models.user import User


def run():
    db = SessionLocal()
    updated = 0
    cleared_only = 0
    try:
        # 1) Encrypt legacy plain numbers
        candidates = (
            db.query(User)
            .filter(User.phone_encrypted.is_(None), User.phone.isnot(None))
            .all()
        )
        for u in candidates:
            try:
                u.set_phone(u.phone)
                updated += 1
            except Exception:
                continue

        # 2) Clear leftover plain column when encrypted exists
        leftovers = (
            db.query(User)
            .filter(User.phone_encrypted.isnot(None), User.phone.isnot(None))
            .all()
        )
        for u in leftovers:
            try:
                u.phone = None
                cleared_only += 1
            except Exception:
                continue

        db.commit()
    finally:
        db.close()

    print({
        "migrated": updated,
        "cleared_plain_only": cleared_only,
    })


if __name__ == "__main__":
    run()

