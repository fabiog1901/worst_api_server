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


def build_model_tuple(fields: list[dict], is_overview: bool = False) -> dict:
    def get_type(x):
        return {
            "string": str,
            "integer": int,
            "date": dt.datetime,
            "decimal": float,
            "null": None,
        }[x]

    def get_fieldinfo(meta: dict):
        fi = FieldInfo()
        if meta.get("default", None):
            fi.default = meta["default"]
        fi.metadata = fi._collect_metadata(meta)
        return fi

    pyd_fields = {}
    for f in fields:
        if not is_overview or (is_overview and f["in_overview"]):
            if f["nullable"]:
                pyd_fields[f["name"]] = (get_type(f["type"]) | None), get_fieldinfo(
                    f["args"]
                )
            else:
                pyd_fields[f["name"]] = (get_type(f["type"]), get_fieldinfo(f["args"]))

    return pyd_fields


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
        rs = cur.execute("SELECT name, skema FROM worst_models", ()).fetchall()
        skemas: dict = {}
        if rs:
            for n, s in rs:
                skemas[n] = s


# for each model, create the Pydantic models


class AuditFields(BaseModel):
    created_by: str | None = None
    created_at: dt.datetime | None = None
    updated_by: str
    updated_at: dt.datetime


class BaseFields(BaseModel):
    id: UUID | None = None
    name: str | None = Field(default="", max_length=50)
    owned_by: str | None = None
    permissions: str | None = None
    tags: set[str] | None = None
    parent_type: str | None = None
    parent_id: UUID | None = None


class Attachments(BaseModel):
    attachments: list[str] = []


pyd_models: dict = {}

for n, s in skemas.items():
    pyd_models[n] = {}

    # ModelUpdate
    f = build_model_tuple(s["fields"])
    model_update = extend_model(f"{n}Update", BaseFields, f)
    pyd_models[n]["update"] = model_update

    # Model
    model = extend_model(n, (model_update, AuditFields, Attachments), {})
    pyd_models[n]["default"] = model

    # # ModelOverview
    f = build_model_tuple(s["fields"], True)
    model = extend_model(f"{n}Overview", (BaseFields, AuditFields), f)
    pyd_models[n]["overview"] = model


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


class Skema(BaseModel):
    svg_path: str = ""
    fields: list[dict]


class ModelUpdate(BaseModel):
    name: str
    skema: Skema


class Model(ModelUpdate, AuditFields):
    pass
