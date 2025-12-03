import asyncio
import secrets
from datetime import date
import sys

from database import init_db, AsyncSessionLocal
from models import ApiKey

async def create_token(owner_name: str):
    # Ensure DB tables exist
    await init_db()
    
    new_token = secrets.token_urlsafe(32)
    
    async with AsyncSessionLocal() as session:
        api_key = ApiKey(
            key=new_token,
            owner=owner_name,
            is_active=True,
            created_at=date.today()
        )
        session.add(api_key)
        await session.commit()
        print(f"\nToken created successfully for '{owner_name}'")
        print(f"Token: {new_token}")
        print(f"Header: Authorization: Bearer {new_token}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python manage_tokens.py <owner_name>")
        sys.exit(1)
    
    owner = sys.argv[1]
    asyncio.run(create_token(owner))
