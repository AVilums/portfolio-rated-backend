import hashlib
import hmac
import secrets

PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PASSWORD_ITERATIONS)
    return "$".join((str(PASSWORD_ITERATIONS), salt, digest.hex()))


def verify_password(password: str, encoded: str) -> bool:
    iterations, salt, expected = encoded.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
