"""Creates an executive (platform-level) login.

An executive sits above every company admin: they belong to no company, and instead
pick which company to view from a dropdown in the app. Deliberately not self-serve —
you cannot sign up as one, it has to be created here.

    python scripts/create_executive.py exec@yourcompany.com "StrongPassword1!" "Sovik Roy"
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.schema_sync import sync_schema  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.seed import seed_roles_and_permissions  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.models.enums import RoleName  # noqa: E402
from app.services import auth_service  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else "Executive"
    first, _, last = full_name.partition(" ")

    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    Base.metadata.create_all(bind=engine)
    sync_schema(engine)

    with SessionLocal() as db:
        seed_roles_and_permissions(db)

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(password),
                first_name=first or "Executive",
                last_name=last or None,
                company_id=None,  # platform level — belongs to no single tenant
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
            db.flush()
            action = "Created"
        else:
            user.password_hash = hash_password(password)
            user.is_active = True
            action = "Updated"

        auth_service.assign_role(db, user, RoleName.SUPER_ADMIN)
        db.commit()

    print(
        f"""
{'=' * 58}
  {action} executive account
{'=' * 58}

  Email     {email}
  Password  {password}

  Sign in at the normal login screen. A company picker appears in
  the top bar — choose any company to see its data with the same
  screens an admin sees.
{'=' * 58}
"""
    )


if __name__ == "__main__":
    main()
