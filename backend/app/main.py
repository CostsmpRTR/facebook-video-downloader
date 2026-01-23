"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import logger
from app.api.routes import video
from app.schemas.video import HealthResponse


def create_application() -> FastAPI:
    """Create and configure the FastAPI application"""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc"
    )
    
    # Configure CORS with specific allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:8000",
            "https://facebook-video-downloader-navy.vercel.app",
            "https://f-down.vercel.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Include routers
    app.include_router(
        video.router,
        prefix=settings.API_V1_STR,
        tags=["video"]
    )
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Health check endpoint"""
        return HealthResponse(
            status="healthy",
            version=settings.VERSION
        )
    
    logger.info(f"Application {settings.PROJECT_NAME} v{settings.VERSION} started")
    
    return app


app = create_application()
