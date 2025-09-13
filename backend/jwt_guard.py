import os, time, typing
from fastapi import Request
from jwt import decode as jwt_decode, InvalidTokenError

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_AUD = os.getenv("JWT_AUDIENCE", "alsadika-clients")
JWT_ISS = os.getenv("JWT_ISSUER", "alsadika-backend")

EXEMPT_PATHS = {
    "/api/health",
    "/openapi.json",
    "/docs",
    "/redoc",
    # flux SSE anonyme si vous voulez tester sans token :
    # "/api/chat/stream",
}

async def verify_request(request: Request) -> bool:
    path = request.url.path
    if any(path == p or path.startswith(p.rstrip("/")) for p in EXEMPT_PATHS):
        return True
    auth = request.headers.get("Authorization","")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ",1)[1].strip()
    try:
        payload = jwt_decode(token, JWT_SECRET, algorithms=["HS256"], audience=JWT_AUD, issuer=JWT_ISS)
        # on pourrait vérifier des scopes ici
        return True
    except InvalidTokenError:
        return False
