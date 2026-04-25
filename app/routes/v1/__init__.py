from fastapi import APIRouter

from app.routes.v1.ai import router as ai_router

router = APIRouter()
router.include_router(ai_router)
