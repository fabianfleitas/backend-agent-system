from fastapi import APIRouter

from app.api.admin.routes import router as admin_router
from app.api.admin.categories_routes import router as categories_router
from app.api.platform.routes import router as platform_router
from app.api.chat.routes import router as chat_router
from app.api.conversations.routes import router as conversations_router


router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(categories_router, prefix="/admin", tags=["categories"])
router.include_router(platform_router, prefix="/platform", tags=["platform"])
