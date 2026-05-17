"""NTP time sync endpoint."""
from fastapi import APIRouter
from app.services.ntp_sync import get_ntp_offset

router = APIRouter(prefix="/api/ntp", tags=["NTP"])


@router.get("/sync")
async def ntp_sync():
    """Sync with NTP servers and return time offset."""
    result = await get_ntp_offset()
    return result
