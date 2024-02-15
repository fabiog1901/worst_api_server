from fastapi import APIRouter, Security, BackgroundTasks, Body
from typing import Annotated
from apiserver.models import User, Report
import inspect
import apiserver.dependencies as dep
import apiserver.service as svc
import datetime as dt
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse
from uuid import UUID


NAME = __name__.split(".", 2)[-1]

router = APIRouter(
    prefix=f"/{NAME}",
    tags=[NAME],
)


@router.get(
    "/{model_name}/{id}",
    dependencies=[Security(dep.get_current_user, scopes=["worst_attachments_list"])],
    description="Required permission: `worst_attachments_list`",
)
async def get_attachment_list(
    model_name: str,
    id: UUID,
) -> list[str] | None:
    s3_folder_name = "/".join([model_name, str(id)])
    return dep.s3_list_all_objects(s3_folder_name)


@router.get(
    "/{model_name}/{id}/presigned-get-url",
    name="Get pre-signed URL for downloading an attachment",
    dependencies=[
        Security(dep.get_current_user, scopes=["worst_attachments_download"])
    ],
    description="Required permission: `worst_attachments_download`",
)
async def get_presigned_get_url(
    model_name: str,
    id: UUID,
    filename: str,
):
    s3_object_name = "/".join([model_name, str(id), filename])
    data = dep.get_presigned_get_url(s3_object_name)
    return HTMLResponse(content=data)


@router.get(
    "/{model_name}/{id}/presigned-put-url",
    name="Get pre-signed URL for uploading an attachment",
    description="Required permission: `worst_attachments_upload`",
)
async def get_presigned_put_url(
    model_name: str,
    id: UUID,
    filename: str,
    current_user: Annotated[
        User, Security(dep.get_current_user, scopes=["worst_attachments_upload"])
    ],
    bg_task: BackgroundTasks,
):
    s3_object_name = "/".join([model_name, str(id), filename])
    attachments = svc.add_attachment(model_name, id, filename)
    data = dep.get_presigned_put_url(s3_object_name)

    if data:
        bg_task.add_task(
            svc.log_event,
            model_name,
            dt.datetime.utcnow(),
            current_user,
            inspect.currentframe().f_code.co_name,  # type: ignore
            s3_object_name,
        )

        # this should append to the new list...
        bg_task.add_task(
            svc.update_documents,
            [{"comp_id": model_name + "_" + str(id), "attachments": attachments}],
        )
    return HTMLResponse(content=data)


@router.delete(
    "/{model_name}/{id}",
    description="Required permission: `worst_attachments_download`",
)
async def delete_attachement(
    model_name: str,
    id: UUID,
    filename: str,
    current_user: Annotated[
        User, Security(dep.get_current_user, scopes=["worst_attachments_delete"])
    ],
    bg_task: BackgroundTasks,
):
    s3_object_name = "/".join([model_name, str(id), filename])
    attachments = svc.remove_attachment(model_name, id, filename)
    dep.s3_remove_object(s3_object_name)

    bg_task.add_task(
        svc.log_event,
        model_name,
        dt.datetime.utcnow(),
        current_user,
        inspect.currentframe().f_code.co_name,  # type: ignore
        s3_object_name,
    )

    # this should add the new list
    bg_task.add_task(
        svc.update_documents,
        [{"comp_id": model_name + "_" + str(id), "attachments": attachments}],
    )
