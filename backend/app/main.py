from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    billing_plan,
    browser_agent,
    bills,
    health,
    negotiations,
    playbooks,
    profile,
    receipts,
    telephony,
)
from app.security import check_jwks_reachable
from app.services import supabase_store
from app.store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Loud on boot beats a silent 401 for every user.
    await check_jwks_reachable()
    yield
    # Release the pooled Supabase connection rather than leaving sockets to the
    # process teardown.
    await supabase_store.aclose()


app = FastAPI(title="Orion Backend", lifespan=lifespan)

# Restricted to settings.allowed_origins_list (default: the frontend's local
# dev origin only) - set ALLOWED_ORIGINS to the real deployed frontend URL(s)
# in production. Previously allow_origins=["*"], a dev-convenience default the
# architecture doc calls out as something to fix before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(bills.router)
app.include_router(negotiations.router)
app.include_router(playbooks.router)
app.include_router(telephony.router)
app.include_router(browser_agent.router)
app.include_router(receipts.router)
app.include_router(profile.router)
app.include_router(billing_plan.router)
