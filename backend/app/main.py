# FastAPI Main Application for Creatio Marketplace
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import Base, engine
from .routes import (
    auth_router,
    gigs_router,
    wallet_router,
    messages_router,
    disputes_router,
    notifications_router,
    analytics_router
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Creatio Marketplace API",
    description="Premium marketplace for the creator economy - connecting creators to businesses",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(gigs_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(disputes_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "Creatio Marketplace",
        "version": "1.0.0",
        "description": "Premium marketplace for the creator economy",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
