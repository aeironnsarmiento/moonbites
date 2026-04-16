from fastapi import APIRouter

from .extract import router as extract_router
from .recipes import router as recipes_router


router = APIRouter()
router.include_router(extract_router)
router.include_router(recipes_router)

__all__ = ["router"]