from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.models import Account, async_session
from app.api.auth import _fetch_user_info, _save_login_state
from app.core.response import ErrorCode, fail

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


class ImportCookieRequest(BaseModel):
    cookie: str = ""
    cookies: str = ""
    game: str = "原神"

@router.get("")
async def list_accounts():
    async with async_session() as db:
        result = await db.execute(select(Account).order_by(Account.id))
        accounts = result.scalars().all()
        items = []
        for account in accounts:
            user_info = await _fetch_user_info(account.cookies) if account.cookies else {}
            cookie_valid = bool(user_info.get("uid"))
            items.append({
                "id": account.id,
                "username": user_info.get("username") or account.username,
                "uid": user_info.get("uid") or account.uid or "",
                "avatar": user_info.get("avatar") or "",
                "game": account.game,
                "is_login": account.is_login,
                "status": "active" if cookie_valid else "expired",
                "cookie_valid": cookie_valid,
                "last_used": account.updated_at or account.created_at,
                "created_at": account.created_at,
            })
        return {"accounts": items, "count": len(items)}

@router.post("")
async def create_account(username: str, cookies: str = "", game: str = "原神"):
    async with async_session() as db:
        acc = Account(username=username, cookies=cookies, game=game)
        db.add(acc); await db.commit(); await db.refresh(acc)
        return {"id": acc.id, "username": acc.username}


@router.post("/import")
async def import_cookie(req: ImportCookieRequest):
    cookies = (req.cookie or req.cookies or "").strip()
    if not cookies:
        return fail(ErrorCode.PARAM_INVALID, msg="缺少 Cookie")

    user_info = await _fetch_user_info(cookies)
    if not user_info.get("uid"):
        return fail(ErrorCode.BILI_COOKIE_INVALID, msg="Cookie 无效或已过期")

    payload = await _save_login_state(cookies, user_info)
    async with async_session() as db:
        result = await db.execute(select(Account).where(Account.uid == payload["uid"]))
        acc = result.scalar_one_or_none()
        if acc:
            acc.game = req.game
            await db.commit()
    return {"code": 0, "msg": "导入成功", "data": payload}

@router.delete("/{account_id}")
async def delete_account(account_id: int):
    async with async_session() as db:
        acc = await db.get(Account, account_id)
        if not acc: raise HTTPException(status_code=404, detail="Not found")
        await db.delete(acc); await db.commit()
    return {"status": "deleted"}
