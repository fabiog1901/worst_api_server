from fastapi import APIRouter, Depends, Security
from uuid import UUID
from typing import Annotated
from worst_crm import db
import worst_crm.dependencies as dep
from worst_crm.models import Account, NewAccount, User, AccountInDB
import json

router = APIRouter(
    prefix="/accounts",
    dependencies=[Depends(dep.get_current_active_user)],
    tags=["accounts"],
)


@router.get("")
async def get_all_accounts() -> list[Account]:
    return db.get_all_accounts()


@router.get("/{account_id}")
async def get_account(account_id: UUID) -> Account | None:
    return db.get_account(account_id)


@router.post("", dependencies=[Security(dep.get_current_active_user, scopes=["rw"])])
async def create_account(
    account: NewAccount,
    current_user: Annotated[User, Depends(dep.get_current_active_user)],
) -> Account | None:
       
    acc_in_db = AccountInDB(
        **account.dict(exclude={'data'}), 
        data=json.dumps(account.data), 
        created_by=current_user.user_id, 
        updated_by=current_user.user_id
    )
  
    return db.create_account(acc_in_db)


@router.put(
    "/{account_id}", dependencies=[Security(dep.get_current_active_user, scopes=["rw"])]
)
async def update_account(
    account_id: UUID, 
    account: NewAccount,
    current_user: Annotated[User, Depends(dep.get_current_active_user)]
) -> Account | None:
    
    acc_in_db = AccountInDB(
        **account.dict(exclude={'data'}), 
        data=json.dumps(account.data), 
        created_by=current_user.user_id, 
        updated_by=current_user.user_id
    )
    return db.update_account(account_id, acc_in_db)


@router.delete(
    "/{account_id}", dependencies=[Security(dep.get_current_active_user, scopes=["rw"])]
)
async def delete_account(account_id: UUID) -> Account | None:
    return db.delete_account(account_id)