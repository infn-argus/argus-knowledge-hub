"""Admin script: grant global admin rights to a user by email.

The target must have signed in at least once already (a User row is only
created on first successful OIDC login) — this is the one manual step needed
to bootstrap the very first admin; every admin after that can be granted
through the app itself.

Usage: python scripts/grant_admin.py <email>
"""
import sys

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1]
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user found with email {email!r} — they must sign in at least once first.")
            sys.exit(1)
        user.is_admin = True
        db.commit()
        print(f"{email} ({user.id}) is now an admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
