from fastapi import APIRouter

from app.api.v1.pnl import router as pnl_router
from app.api.v1.positions import router as positions_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.uploads import router as uploads_router

router = APIRouter()

router.include_router(uploads_router)
router.include_router(transactions_router)
router.include_router(positions_router)
router.include_router(pnl_router)
