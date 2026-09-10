"""Create an account explicitly; never change an existing password on startup."""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_platform.auth import Credentials, hash_password
from risk_platform.database import engine
from risk_platform.models import User


def main() -> None:
    credentials = Credentials(
        email=os.environ["INITIAL_EMAIL"], password=os.environ["INITIAL_PASSWORD"]
    )
    if len(credentials.password) < 12:
        raise ValueError("Initial password must contain at least 12 characters.")
    with Session(engine) as db:
        if db.scalar(select(User).where(User.email == credentials.email)) is None:
            db.add(User(email=credentials.email, password_hash=hash_password(credentials.password)))
            db.commit()


if __name__ == "__main__":
    main()
