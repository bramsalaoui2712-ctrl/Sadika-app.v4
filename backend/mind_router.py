from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
def mind_health():
    return {"mind":"ok","ts":datetime.utcnow().isoformat()}

