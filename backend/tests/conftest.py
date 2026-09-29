import os

# Integration tests must never touch the dev database.
# If TEST_DATABASE_URL is given, point the whole app at it BEFORE anything imports settings.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL