import os
import libsql_client
from dotenv import load_dotenv

load_dotenv()

TURSO_URL = os.environ["TURSO_DATABASE_URL"]
TURSO_TOKEN = os.environ["TURSO_AUTH_TOKEN"]


async def get_client():
    return libsql_client.create_client(
        url=TURSO_URL,
        auth_token=TURSO_TOKEN,
    )
