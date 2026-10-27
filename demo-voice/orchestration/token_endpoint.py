#!/usr/bin/env python3
"""
Voice Demo Token Endpoint

Layer 2: Orchestration - Exchanges the secret Vocal Bridge API key for a
short-lived session token, so the browser never sees the key.
"""

import os
import logging

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
VOCAL_BRIDGE_URL = "https://vocalbridgeai.com/api/v1/token"
VOCAL_BRIDGE_API_KEY = os.getenv("VOCAL_BRIDGE_API_KEY")
DEFAULT_AGENT = "voice-demo"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "https://miagentuca.es,http://localhost:5173").split(",")
    if o.strip()
]
PARTICIPANT_NAME = "Visitante web"

logger = logging.getLogger("demo-voice")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def load_agents() -> dict[str, str]:
    """Parse VOCAL_BRIDGE_AGENTS ("name:agent_id,...") into {name: agent_id}.

    VOCAL_BRIDGE_AGENT_ID_VOICE stays as the fallback for "voice-demo".
    """
    agents = {}
    for pair in os.getenv("VOCAL_BRIDGE_AGENTS", "").split(","):
        if not pair.strip():
            continue
        name, _, agent_id = pair.partition(":")
        name, agent_id = name.strip(), agent_id.strip()
        if not name or not agent_id:
            logger.warning("Ignoring malformed VOCAL_BRIDGE_AGENTS entry (expected name:agent_id)")
            continue
        agents[name] = agent_id

    legacy_id = os.getenv("VOCAL_BRIDGE_AGENT_ID_VOICE", "").strip()
    if DEFAULT_AGENT not in agents and legacy_id:
        agents[DEFAULT_AGENT] = legacy_id
    return agents


AGENTS = load_agents()
if not AGENTS:
    logger.error("No Vocal Bridge agent configured: set VOCAL_BRIDGE_AGENTS or VOCAL_BRIDGE_AGENT_ID_VOICE")
    raise SystemExit(1)
logger.info("Configured agents: %s", ", ".join(AGENTS))

# Initialize FastAPI
app = FastAPI(
    title="Demo Voice - Vocal Bridge Token Service",
    description="Mints short-lived Vocal Bridge session tokens for the voice agent on miagentuca.es",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_real_ip(request: Request) -> str:
    """Extract real client IP behind reverse proxy (Traefik/Nginx)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "127.0.0.1"


# Rate limiting - every token starts a billable voice session, so this is the cost guard
TOKEN_RATE_LIMIT = "5/hour"
limiter = Limiter(key_func=get_real_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/token")
@limiter.limit(TOKEN_RATE_LIMIT)
async def mint_token(request: Request):
    """Ask Vocal Bridge for a session token and return only what the browser needs."""
    agent_id = AGENTS.get(DEFAULT_AGENT)
    if not VOCAL_BRIDGE_API_KEY or not agent_id:
        logger.error("Vocal Bridge credentials not configured")
        raise HTTPException(status_code=502, detail="Voice service unavailable")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                VOCAL_BRIDGE_URL,
                headers={
                    "X-API-Key": VOCAL_BRIDGE_API_KEY,
                    "X-Agent-Id": agent_id,
                    "Content-Type": "application/json",
                },
                json={"participant_name": PARTICIPANT_NAME},
            )
        res.raise_for_status()
        data = res.json()
        return {
            "connection_url": data.get("connection_url") or data["livekit_url"],
            "token": data["token"],
            "session_name": data["room_name"],
            "agent_mode": data.get("agent_mode", ""),
        }
    except httpx.HTTPStatusError as e:
        # Log only the status code: the response body could echo credentials
        logger.error("Vocal Bridge returned HTTP %s", e.response.status_code)
    except httpx.HTTPError as e:
        logger.error("Vocal Bridge request failed: %s", type(e).__name__)
    except (ValueError, KeyError) as e:
        logger.error("Unexpected Vocal Bridge response: %s", type(e).__name__)
    raise HTTPException(status_code=502, detail="Voice service unavailable")
