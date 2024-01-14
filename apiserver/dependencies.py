from apiserver import db
from apiserver.models import UserInDB
from fastapi import Depends, HTTPException, status, BackgroundTasks, APIRouter
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt
from jwt.algorithms import RSAAlgorithm
from minio.deleteobjects import DeleteObject
from passlib.context import CryptContext
from typing import Annotated
import datetime as dt
import json
import minio
import os
import validators


JWKS = os.getenv("JWKS")
ALGORITHM = os.getenv("ALGORITHM")

if not JWKS or not ALGORITHM:
    raise EnvironmentError("JWKS or ALGORITHM env variables not found!")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login", scopes={"rw": "rw", "admin": "admin"}
)


S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_USE_SECURE_TLS = (
    True
    if os.getenv("S3_USE_SECURE_TLS", "True").lower()
    in ["true", "1", "t", "y", "yes", "on"]
    else False
)
S3_BUCKET = os.getenv("S3_BUCKET")
S3_PRESIGNED_URL_EXPIRY_SECONDS = int(os.getenv("S3_PRESIGNED_URL_EXPIRY_SECONDS", 5))

minio_client = minio.Minio(
    endpoint=S3_ENDPOINT_URL,
    secure=S3_USE_SECURE_TLS,
    access_key=S3_ACCESS_KEY,
    secret_key=S3_SECRET_KEY,
)


def get_api_router(name: str) -> APIRouter:
    return APIRouter(
        prefix=f"/{name}",
        tags=[name],
    )


def get_presigned_get_url(filename: str) -> str:
    data = minio_client.presigned_get_object(
        S3_BUCKET,
        filename,
        expires=dt.timedelta(seconds=S3_PRESIGNED_URL_EXPIRY_SECONDS),
    )

    if validators.url(data):  # type: ignore
        return data
    else:
        raise ValueError(f"Could not generate presigned-get-url for {filename}")


def get_presigned_put_url(filename: str):
    data = minio_client.presigned_put_object(
        S3_BUCKET,
        filename,
        expires=dt.timedelta(seconds=S3_PRESIGNED_URL_EXPIRY_SECONDS),
    )

    if validators.url(data):  # type: ignore
        return data
    else:
        raise ValueError(f"Could not generate presigned-put-url for {filename}")


def s3_remove_object(filename: str):
    minio_client.remove_object(S3_BUCKET, filename)


def s3_list_all_objects(folder: str) -> list[str]:
    return [
        x.object_name
        for x in minio_client.list_objects(S3_BUCKET, folder, recursive=True)
    ]


def s3_delete_all_objects(folder: str):
    delete_object_list = map(
        lambda x: DeleteObject(x.object_name),
        minio_client.list_objects(S3_BUCKET, folder, recursive=True),
    )

    errors = minio_client.remove_objects(S3_BUCKET, delete_object_list)
    for _ in errors:
        pass


def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
):
    unverified_header = jwt.get_unverified_header(token)

    rsa_key = {}
    for key in json.loads(JWKS)["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }

    if rsa_key:
        print("rsa")
        try:
            public_key = RSAAlgorithm.from_jwk(rsa_key)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=ALGORITHM,
                options=dict(
                    verify_aud=False,
                    verify_sub=False,
                    verify_exp=False,
                ),
            )

        except jwt.ExpiredSignatureError:
            print("129")
            raise HTTPException(
                {"code": "token_expired", "description": "token is expired"}, 401
            )

        except Exception as e:
            print("135")
            raise HTTPException(401, f"Unable to parse authentication token: {e.args}" )

        # Check that we all scopes are present
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid authorization token")

    token_scopes = payload.get("scope", "").split()

    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            print("155 token issue")
    #         raise HTTPException(
    #             {
    #                 "code": "Unauthorized",
    #                 "description": f"You don't have access to this resource. `{' '.join(security_scopes.scopes)}` scopes required",
    #             },
    #             403,
    #         )

    return payload
