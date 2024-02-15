from fastapi import APIRouter, Security, Body
from typing import Annotated, Any
import apiserver.dependencies as dep
import apiserver.service as svc
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

NAME = __name__.split(".", 2)[-1]

router = APIRouter(
    prefix=f"/{NAME}",
    tags=[NAME],
)


@router.post(
    "/multi-search",
    dependencies=[Security(dep.get_current_user, scopes=["worst_search"])],
    description="Required permission: `worst_search`",
)
async def execute_search(
    search_queries: Annotated[dict, Body()],
) -> dict | None:
    return svc.execute_search(search_queries["queries"])
