"""A very small limit on wrong passwords, so nobody can guess a password thousands of times.

Rule: 5 wrong attempts for the same email within 15 minutes -> that email must wait.
It lives in the server's memory, so a restart resets it. That is fine for one server;
a bigger app would keep these counts in a shared store.
"""
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

failed_logins = {}   # email -> list of times (seconds) of recent wrong attempts


def _recent_failures(email: str):
    now = time.time()
    recent = [t for t in failed_logins.get(email, []) if now - t < WINDOW_SECONDS]
    failed_logins[email] = recent
    return recent


def seconds_to_wait(email: str) -> int:
    """0 if the email may try now, otherwise how many seconds until it may."""
    recent = _recent_failures(email)
    if len(recent) < MAX_FAILURES:
        return 0
    return int(WINDOW_SECONDS - (time.time() - recent[0])) + 1


def record_failure(email: str):
    _recent_failures(email).append(time.time())


def clear(email: str):
    failed_logins.pop(email, None)