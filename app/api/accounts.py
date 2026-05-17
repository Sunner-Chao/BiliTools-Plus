from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from app.models import Account, async_session

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])

@router.get("")
async def list_accounts():
    async with async_session() as db:
        result = await db.execute(select(Account).order_by(Account.id))
        accounts = result.scalars().all()
        return {"accounts": [{"id": a.id, "username": a.username, "game": a.game, "is_login": a.is_login, "created_at": a.created_at} for a in accounts], "count": len(accounts)}

@router.post("")
async def create_account(username: str, cookies: str = "", game: str = "原神"):
    async with async_session() as db:
        acc = Account(username=username, cookies=cookies, game=game)
        db.add(acc); await db.commit(); await db.refresh(acc)
        return {"id": acc.id, "username": acc.username}

@router.delete("/{account_id}")
async def delete_account(account_id: int):
    async with async_session() as db:
        acc = await db.get(Account, account_id)
        if not acc: raise HTTPException(status_code=404, detail="Not found")
        await db.delete(acc); await db.commit()
    return {"status": "deleted"}
