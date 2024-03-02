from apiserver import db
from apiserver.routers import sql, search, reports, models, attachments
from apiserver.worstrouter import WorstRouter
from apiserver.models import (
    pyd_models,
    Token,
    User,
)
from fastapi import FastAPI, Depends, HTTPException, Query, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Annotated
import apiserver.dependencies as dep
import apiserver.service as svc
import hashlib
import os
import requests
import threading
import time
import urllib.parse as parse

AUTH_ENDPOINT = os.getenv("AUTH_ENDPOINT")
TOKEN_ENDPOINT = os.getenv("TOKEN_ENDPOINT")
SCOPE = os.getenv("SCOPE")
CLIENT_ID = os.getenv("CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")


SCOPE_CLAIM = os.getenv("SCOPE_CLAIM")
USERNAME_CLAIM = os.getenv("USERNAME_CLAIM")
FULLNAME_CLAIM = os.getenv("FULLNAME_CLAIM")
EMAIL_CLAIM = os.getenv("EMAIL_CLAIM")

# to get a string like this run:
# openssl rand -hex 32
JWT_KEY = os.getenv("JWT_KEY")
JWT_KEY_ALGORITHM = os.getenv("JWT_KEY_ALGORITHM")
JWT_EXPIRY_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", 1800))


app = FastAPI(
    title="Worst API",
    version="0.1.0",
    docs_url="/api",
    openapi_url="/worst.openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://localhost:5500/app",
        "http://localhost",
        "http://localhost/app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/healthcheck",
)
async def healthcheck() -> dict:
    return {"hello": "worst"}


@app.get(
    "/auth_config",
    tags=["auth"],
)
async def get_authorization_config() -> dict:
    return {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "authorization_endpoint": AUTH_ENDPOINT,
        "token_endpoint": TOKEN_ENDPOINT,
        "requested_scopes": SCOPE,
    }


# add routers dynamically
for k, v in pyd_models.items():
    app.include_router(
        WorstRouter(
            instance_type=k,
            default_model=v["default"],
            overview_model=v["overview"],
            update_model=v["update"],
        )
    )


app.include_router(attachments.router)
app.include_router(sql.router)
app.include_router(search.router)
app.include_router(reports.router)
app.include_router(models.router)


# uvicorn server is started and configured to reload
# if file 'watch.txt' changes.
# Thus, whenever the app wants to instruct uvicorn to reboot itself,
# it just has to touch that file.
# To make sure that every instance of the app reboots,
# the app updates a db entry that is periodically fetched by
# every instance. If the value is different than the initial value,
# the app touches file watch.txt which will cause uvicorn to reload the app.

# store initial value at startup
watch_epoch = db.get_watch()


def watch_it(watch_epoch: int):
    while True:
        if db.get_watch() > watch_epoch:
            Path("watch.txt").touch()

        time.sleep(15)


# periodically check if a restart is needed
threading.Thread(target=watch_it, args=(watch_epoch,), daemon=True).start()
