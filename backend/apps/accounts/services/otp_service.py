import hashlib
import hmac
import secrets

import django_redis
from django.conf import settings
from redis import Redis


def _get_redis() -> Redis:
    """
    Retrieves a Redis connection instance configured via Django's
    django_redis library.

    :return: A Redis connection object.
    :rtype: Redis
    """
    return django_redis.get_redis_connection()


def _hash_otp(otp: str) -> str:
    """
    Generates a SHA-256 hash for the provided one-time password (OTP).

    This function is used to compute a secure, irreversible hash for a given OTP
    string. The resulting hash can be stored and compared for authentication
    purposes without exposing the original OTP value.

    :param otp: A string representing the one-time password to be hashed.
    :return: A string containing the SHA-256 hash of the provided OTP.
    """
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_otp(phone_number: str):
    """
    Generates a One-Time Password (OTP) and handles the associated rate limiting and storage
    mechanisms. The OTP is securely hashed and stored, ensuring it expires after a configured
    time period. This function also enforces rate limits to prevent abuse.

    :param phone_number: The phone number for which the OTP is being generated.
    :type phone_number: str
    :return: The generated OTP as a string.
    :rtype: str
    :raises ValueError: If the rate limit for OTP requests is exceeded.
    """
    redis = _get_redis()

    # rate limiting
    rate_key = f"otp:rate:{phone_number}"
    current_rate = redis.get(rate_key)

    if current_rate and int(current_rate) >= settings.OTP_RATE_LIMIT:  # type: ignore[assignment]
        raise ValueError("Too many OTP requests. Try again in a few minutes.")

    shift = 10**settings.OTP_LENGTH
    upper_threshold = 9 * shift

    otp = f"{secrets.randbelow(upper_threshold) + shift}"

    # store hashed otp in redis
    code_key = f"otp:code:{phone_number}"
    attempts_key = f"otp:attempts:{phone_number}"

    pipe = redis.pipeline()

    # store the hashed OTP with TTL
    pipe.setex(code_key, settings.OTP_EXPIRY_SECONDS, _hash_otp(otp))

    # reset the attempt counter with same TTL
    pipe.setex(attempts_key, settings.OTP_EXPIRY_SECONDS, 0)

    # increment the rate limiter (or create with TTL if new)
    pipe.incr(rate_key)

    # Set TTL on rate key only if it's new (INCR creates without TTL)
    pipe.expire(rate_key, settings.OTP_RATE_LIMIT_WINDOW)

    pipe.execute()

    return otp


def verify_otp(phone_number: str, otp: str) -> bool:
    """
    Verify the provided OTP against the stored OTP in the system, ensuring secure and constant-time
    verification to prevent timing attacks. The function also manages OTP expiration
    and limits the number of verification attempts.

    :param phone_number: The phone number associated with the OTP to be verified.
    :type phone_number: str
    :param otp: The OTP entered by the user for verification.
    :type otp: str
    :return: A boolean indicating whether the OTP verification was successful or not.
    :rtype: bool
    :raises ValueError: If the OTP has expired, was never sent, has too many incorrect attempts,
        or if the provided OTP is incorrect.
    """
    redis = _get_redis()

    code_key = f"otp:code:{phone_number}"
    attempts_key = f"otp:attempts:{phone_number}"

    # check if otp exists
    stored_hash = redis.get(code_key)

    if not stored_hash:
        raise ValueError("OTP has expired or was never sent. Request a new one.")

    if isinstance(stored_hash, bytes):
        stored_hash = stored_hash.decode()

    # check attempt count
    attempts: bytes | None = redis.get(attempts_key)  # type: ignore[assignment]
    attempt_count = int(attempts) if attempts else 0

    if attempt_count >= settings.OTP_MAX_ATTEMPTS:
        redis.delete(code_key, attempts_key)
        raise ValueError("Too many incorrect attempts. Request a new OTP.")

    # verify OTP (constant-time comparison)
    provided_hash = _hash_otp(otp)

    if not hmac.compare_digest(stored_hash, provided_hash):  # type: ignore[arg-type]
        # Increment attempt counter
        redis.incr(attempts_key)
        remaining = settings.OTP_MAX_ATTEMPTS - attempt_count - 1
        raise ValueError(f"Incorrect OTP. {remaining} attempts remaining.")

    # success - clean up
    redis.delete(code_key, attempts_key)

    return True
