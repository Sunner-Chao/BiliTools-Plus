"""NTP time sync service for accurate countdown timing."""
import asyncio
import socket
import struct
import time
from datetime import datetime, timezone


NTP_SERVERS = [
    "ntp.aliyun.com",
    "ntp.tencent.com",
    "cn.ntp.org.cn",
    "pool.ntp.org",
]

NTP_EPOCH = 2208988800  # seconds between 1900-01-01 and 1970-01-01


def _ntp_request(server: str, timeout: float = 3.0) -> float | None:
    """Send NTP request and return offset in milliseconds."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(timeout)
        
        # Build NTP packet (LI=0, VN=4, Mode=3 client)
        packet = b'\x23' + b'\x00' * 47
        t_send = time.time()
        
        client.sendto(packet, (server, 123))
        data, _ = client.recvfrom(1024)
        t_recv = time.time()
        client.close()
        
        # Parse NTP response
        t_transmit = struct.unpack('!II', data[40:48])
        t_transmit = t_transmit[0] + t_transmit[1] / 2**32 - NTP_EPOCH
        
        # Calculate offset: offset = ((t1 - t0) + (t2 - t3)) / 2
        # Simplified: offset = t_transmit - (t_send + t_recv) / 2
        offset_ms = (t_transmit - (t_send + t_recv) / 2) * 1000
        return round(offset_ms, 2)
    except Exception:
        return None


async def get_ntp_offset() -> dict:
    """Get NTP time offset from multiple servers."""
    loop = asyncio.get_event_loop()
    results = []
    
    for server in NTP_SERVERS:
        offset = await loop.run_in_executor(None, _ntp_request, server)
        results.append({
            "server": server,
            "offset_ms": offset,
            "status": "ok" if offset is not None else "timeout",
        })
    
    # Calculate median offset from successful results
    valid_offsets = [r["offset_ms"] for r in results if r["offset_ms"] is not None]
    median_offset = sorted(valid_offsets)[len(valid_offsets) // 2] if valid_offsets else 0
    
    return {
        "offset_ms": median_offset,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "servers": results,
        "success_count": len(valid_offsets),
    }
