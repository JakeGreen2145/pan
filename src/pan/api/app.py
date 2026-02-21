from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pan.api.routes import health, leases, payments, plaid, tenants, units


def create_api() -> FastAPI:
    app = FastAPI(title="Pan Admin API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(units.router, prefix="/api/units", tags=["units"])
    app.include_router(tenants.router, prefix="/api/tenants", tags=["tenants"])
    app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
    app.include_router(plaid.router, prefix="/api/plaid", tags=["plaid"])
    app.include_router(leases.router, prefix="/api/leases", tags=["leases"])

    return app
