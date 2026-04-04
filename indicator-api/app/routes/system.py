from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/")
async def root() -> dict:
    return {"message": "Welcome to the Indicator API"}


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
