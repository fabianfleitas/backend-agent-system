from fastapi import APIRouter

from app.api.admin.routes import router as admin_router
from app.api.student.routes import router as student_router


router = APIRouter()
router.include_router(student_router, prefix="/student", tags=["student"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
