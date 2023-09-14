from enum import Enum
from pydantic import create_model, BaseModel, EmailStr, Field
from pydantic.fields import FieldInfo
from uuid import UUID
import datetime as dt
import os
import psycopg
import re

#############################
#  LOAD MODELS DYNAMICALLY  #
#############################

DB_URL = os.getenv("DB_URL")

if not DB_URL:
    raise EnvironmentError("DB_URL env variable not found!")


def build_model_tuple(d: dict[str, dict[str, dict]]) -> dict:
    def get_type(x):
        return {"string": str, "integer": int, "null": None}[x]

    def get_fieldinfo(meta: dict):
        fi = FieldInfo()
        if meta.get("default", None):
            fi.default = meta["default"]
        fi.metadata = fi._collect_metadata(meta)
        return fi

    fields = {}
    for k, v in d.get("properties", {}).items():
        if v.get("anyOf", None):
            fields[k] = (
                get_type(v["anyOf"][0]["type"]) | get_type(v["anyOf"][1]["type"]),
                get_fieldinfo(v),
            )
        else:
            fields[k] = (get_type(v["type"]), get_fieldinfo(v))

    return fields


def extend_model(name: str, base: type, dict_def: dict):
    fields = {}
    for field_name, value in dict_def.items():
        if isinstance(value, tuple):
            fields[field_name] = value
        elif isinstance(value, dict):
            fields[field_name] = (
                extend_model(f"{name}_{field_name}", base, value),
                ...,
            )
        else:
            raise ValueError(f"Field {field_name}:{value} has invalid syntax")
    return create_model(name, __base__=base, **fields)


# get all model defs from database
with psycopg.connect(DB_URL, autocommit=True) as conn:
    with conn.cursor() as cur:
        rs = cur.execute("SELECT name, skema FROM models", ()).fetchall()
        skemas: dict = {}
        if rs:
            for n, s in rs:
                skemas[n] = s


# for each model, create the Pydantic models

class AuditFields(BaseModel):
    created_by: str | None = None
    created_at: dt.datetime
    updated_by: str | None = None
    updated_at: dt.datetime


class BaseFields(BaseModel):
    id: UUID | None = None
    name: str | None = Field(default="", max_length=50)
    owned_by: str | None = None
    permissions: str | None = None
    attachments: list[str] | None = None
    tags: set[str] | None = None
    parent_type: str | None = None
    parent_id: UUID | None = None


pyd_models: dict = {}

for n, s in skemas.items():
    pyd_models[n] = {}
    
    # ModelUpdate
    f = build_model_tuple(s)
    model_update = extend_model(f"{n}Update", BaseFields, f)
    pyd_models[n]["update"] = model_update

    # Model
    model = extend_model(f"{n}", (model_update, AuditFields), {})
    pyd_models[n]["default"] = model

    # Model
    # model = extend_model(n, (model_in_db, AuditFields), {})
    # pyd_models[n]["return"] = model

    # ModelOverview


###################
#  ADMIN OBJECTS  #
###################
class Token(BaseModel):
    access_token: str
    token_type: str


class CommonUser(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    is_disabled: bool | None = None
    scopes: list[str] | None = None


class User(CommonUser):
    user_id: str


class UpdatedUser(CommonUser):
    password: str | None = None


class UpdatedUserInDB(CommonUser):
    hashed_password: str | None = None


class NewUser(User):
    password: str = Field(min_length=8, max_length=50)


class UserInDB(User):
    hashed_password: str
    failed_attempts: int = 0


###################
#  MODEL OBJECTS  #
###################


class PydanticModel(BaseModel):
    properties: dict
    required: list[str] | None = None
    title: str | None = None
    type: str | None = None


class UpdatedModel(BaseModel):
    name: str
    skema: PydanticModel


class ModelInDB(UpdatedModel, AuditFields):
    pass


class Model(ModelInDB):
    pass
