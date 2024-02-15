from fastapi import APIRouter, Security, BackgroundTasks, Body
from typing import Annotated
from apiserver.models import User, Report
import inspect
import apiserver.dependencies as dep
import apiserver.service as svc
import datetime as dt
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

NAME = __name__.split(".", 2)[-1]

router = APIRouter(
    prefix=f"/{NAME}",
    tags=[NAME],
)


@router.get(
    "",
    dependencies=[Security(dep.get_current_user, scopes=["worst_reports_read"])],
    description="Required permission: `worst_reports_read`",
)
async def get_all_reports() -> list[Report] | None:
    return svc.get_all_reports()


@router.get(
    "/{name}",
    dependencies=[Security(dep.get_current_user, scopes=["worst_reports_read"])],
    description="Required permission: `worst_reports_read`",
)
async def get_report(name: str) -> Report | None:
    return svc.get_report(name)


@router.post(
    "",
    description="Required permission: `worst_reports_create`",
)
async def create_report(
    name: Annotated[str, Body()],
    sql_stmt: Annotated[str, Body()],
    current_user: Annotated[
        User, Security(dep.get_current_user, scopes=["worst_reports_create"])
    ],
    bg_task: BackgroundTasks,
) -> Report | None:
    x = svc.create_report(name, sql_stmt, current_user)

    if x:
        bg_task.add_task(
            svc.log_event,
            NAME,
            dt.datetime.utcnow(),
            current_user,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x


@router.put(
    "/{name}",
    description="Required permission: `worst_reports_update`",
)
async def update_report(
    name: str,
    sql_stmt: Annotated[str, Body()],
    current_user: Annotated[
        User, Security(dep.get_current_user, scopes=["worst_reports_update"])
    ],
    bg_task: BackgroundTasks,
) -> Report | None:
    x = svc.update_report(name, sql_stmt, current_user)

    if x:
        bg_task.add_task(
            svc.log_event,
            NAME,
            dt.datetime.utcnow(),
            current_user,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x


@router.delete(
    "/{name}",
    description="Required permission: `worst_reports_delete`",
)
async def delete_report(
    name: str,
    current_user: Annotated[
        User, Security(dep.get_current_user, scopes=["worst_reports_delete"])
    ],
    bg_task: BackgroundTasks,
) -> Report | None:
    x = svc.delete_report(name)

    if x:
        bg_task.add_task(
            svc.log_event,
            NAME,
            dt.datetime.utcnow(),
            current_user,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x
