from fastapi import APIRouter

from ..auth import router as auth_router
from .extract import router as extract_router
from .recipes import router as recipes_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(extract_router)
router.include_router(recipes_router)

__all__ = ["router"]
