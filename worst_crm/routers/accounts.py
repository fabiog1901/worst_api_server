from typing import Annotated
from fastapi import Security, BackgroundTasks
from fastapi.responses import HTMLResponse
from typing import Annotated
from uuid import UUID, uuid4
from worst_crm import db
from worst_crm.models import (
    Account,
    UpdatedAccount,
    AccountInDB,
    AccountOverview,
    AccountFilters,
    User,
)
import worst_crm.dependencies as dep
import inspect

NAME = __name__.split(".")[-1]

router = dep.get_api_router(NAME)


@router.get(
    "",
    dependencies=[Security(dep.get_current_user)],
)
async def get_all_accounts(
    account_filters: AccountFilters | None = None,
) -> list[AccountOverview]:
    return db.get_all_accounts(account_filters)


@router.get(
    "/{account_id}",
    dependencies=[Security(dep.get_current_user)],
)
async def get_account(
    account_id: UUID,
) -> Account | None:
    return db.get_account(account_id)


@router.post(
    "",
    description="`account_id` will be generated if not provided by client.",
)
async def create_account(
    account: UpdatedAccount,
    current_user: Annotated[User, Security(dep.get_current_user, scopes=["rw"])],
    bg_task: BackgroundTasks,
) -> Account | None:
    acc_in_db = AccountInDB(
        **account.model_dump(exclude_unset=True),
        created_by=current_user.user_id,
        updated_by=current_user.user_id
    )

    if not acc_in_db.account_id:
        acc_in_db.account_id = uuid4()

    x = db.create_account(acc_in_db)

    if x:
        bg_task.add_task(
            db.log_event,
            NAME,
            current_user.user_id,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x


@router.put(
    "",
)
async def update_account(
    account: UpdatedAccount,
    current_user: Annotated[User, Security(dep.get_current_user, scopes=["rw"])],
    bg_task: BackgroundTasks,
) -> Account | None:
    acc_in_db = AccountInDB(
        **account.model_dump(exclude_unset=True), updated_by=current_user.user_id
    )

    x = db.update_account(acc_in_db)

    if x:
        bg_task.add_task(
            db.log_event,
            NAME,
            current_user.user_id,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x


@router.delete(
    "/{account_id}",
)
async def delete_account(
    account_id: UUID,
    current_user: Annotated[User, Security(dep.get_current_user, scopes=["rw"])],
    bg_task: BackgroundTasks,
) -> Account | None:
    x = db.delete_account(account_id)

    if x:
        bg_task.add_task(
            db.log_event,
            NAME,
            current_user.user_id,
            inspect.currentframe().f_code.co_name,  # type: ignore
            x.model_dump_json(),
        )

    return x


# Attachements
@router.get(
    "/{account_id}/presigned-get-url/{filename}",
    name="Get pre-signed URL for downloading an attachment",
    dependencies=[Security(dep.get_current_user)],
)
async def get_presigned_get_url(
    account_id: UUID,
    filename: str,
):
    s3_object_name = str(account_id) + "/" + filename
    data = dep.get_presigned_get_url(s3_object_name)
    return HTMLResponse(content=data)


@router.get(
    "/{account_id}/presigned-put-url/{filename}",
    dependencies=[Security(dep.get_current_user, scopes=["rw"])],
    name="Get pre-signed URL for uploading an attachment",
)
async def get_presigned_put_url(
    account_id: UUID,
    filename: str,
):
    s3_object_name = str(account_id) + "/" + filename
    db.add_account_attachment(account_id, filename)
    data = dep.get_presigned_put_url(s3_object_name)
    return HTMLResponse(content=data)


@router.delete(
    "/{account_id}/attachments/{filename}",
    dependencies=[Security(dep.get_current_user, scopes=["rw"])],
)
async def delete_attachement(
    account_id: UUID,
    filename: str,
):
    s3_object_name = str(account_id) + "/" + filename
    db.remove_account_attachment(account_id, filename)
    dep.s3_remove_object(s3_object_name)
