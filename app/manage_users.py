"""Account administration: python -m app.manage_users create EMAIL (password prompted)."""

import argparse
from getpass import getpass

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.auth_schemas import normalize_email
from app.config import Settings
from app.database import make_database
from app.models import AuthSession, User
from app.services.auth import create_user, new_password_hash


def read_password() -> str:
    value = getpass("Password (12+ characters): ")
    if value != getpass("Repeat password: "):
        raise ValueError("Passwords do not match.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "reset-password", "disable"])
    parser.add_argument("email")
    args = parser.parse_args()
    engine, sessions = make_database(Settings().database_url)
    try:
        email = normalize_email(args.email)
        if args.action == "create":
            create_user(email, read_password(), sessions)
        else:
            encoded = (
                new_password_hash(read_password()) if args.action == "reset-password" else None
            )
            with sessions() as db:
                user = db.scalar(select(User).where(User.email == email))
                if user is None:
                    raise ValueError("Account not found.")
                if encoded:
                    user.password_hash = encoded
                else:
                    user.is_active = False
                db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
                db.commit()
        print("Account updated.")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except SQLAlchemyError:
        parser.exit(1, "Database operation failed. Check DATABASE_URL and run migrations first.\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
