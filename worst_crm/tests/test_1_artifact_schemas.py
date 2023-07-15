from fastapi.testclient import TestClient
from worst_crm.main import app
from worst_crm.models import ArtifactSchema
from worst_crm.tests.utils import login
from faker import Faker
import random

fake = Faker()

client = TestClient(app)

ARTIFACT_SCHEMA_ID = "ART-SCHEMA-1"


def test_get_artifact_schemas_non_auth():
    r = client.get("/artifact_schemas")

    assert r.status_code == 401


def test_create_artifact_schema(login):
    r = client.post(
        "/artifact_schemas",
        headers={"Authorization": f"Bearer {login}"},
        json={
            "artifact_schema_id": ARTIFACT_SCHEMA_ID,
            "artifact_schema": {
                "properties": {
                    "nodes": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "title": "Nodes",
                    },
                    "name": {
                        "default": "cluster-name",
                        "maxLength": 30,
                        "title": "Name",
                        "type": "string",
                    },
                },
                "required": ["nodes"],
                "title": "Cluster",
                "type": "object",
            },
        },
    )

    assert r.status_code == 200
    acc = ArtifactSchema(**r.json())
    assert isinstance(acc, ArtifactSchema)


def test_load_artifact_schemas(login):
    for _ in range(10):
        r = client.post(
            "/artifact_schemas",
            headers={"Authorization": f"Bearer {login}"},
            json={
                "artifact_schema_id": "ARTSCHEMA-" + str(random.randint(000, 999)),
                "artifact_schema": {
                    "properties": {
                        "nodes": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "title": "Nodes",
                        },
                        "name": {
                            "default": "cluster-name",
                            "maxLength": 30,
                            "title": "Name",
                            "type": "string",
                        },
                    },
                    "required": ["nodes"],
                    "title": "Cluster",
                    "type": "object",
                },
            },
        )
        assert r.status_code == 200


def test_update_artifact_schema(login):
    r = client.put(
        f"/artifact_schemas",
        headers={"Authorization": f"Bearer {login}"},
        json={
            "artifact_schema_id": ARTIFACT_SCHEMA_ID,
            "artifact_schema": {
                "properties": {
                    "nodes": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "title": "Nodes",
                    },
                    "name": {
                        "default": "cluster-name",
                        "maxLength": 40,
                        "title": "Name",
                        "type": "string",
                    },
                },
                "required": ["nodes"],
                "title": "Cluster",
                "type": "object",
            },
        },
    )
    assert r.status_code == 200
    upd_acc = ArtifactSchema(**r.json())

    # fetch stored artifact_schema
    r = client.get(
        f"/artifact_schemas/{ARTIFACT_SCHEMA_ID}",
        headers={"Authorization": f"Bearer {login}"},
    )

    assert r.status_code == 200
    acc = ArtifactSchema(**r.json())

    assert upd_acc == acc
    assert acc.artifact_schema == {
        "properties": {
            "nodes": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "title": "Nodes",
            },
            "name": {
                "default": "cluster-name",
                "maxLength": 40,
                "title": "Name",
                "type": "string",
            },
        },
        "required": ["nodes"],
        "title": "Cluster",
        "type": "object",
    }


def test_get_all_artifact_schemas(
    login,
):
    r = client.get(
        "/artifact_schemas",
        headers={"Authorization": f"Bearer {login}"},
    )

    l: list[ArtifactSchema] = [ArtifactSchema(**x) for x in r.json()]

    assert r.status_code == 200
    assert len(l) >= 10


def test_delete_artifact_schema(login):
    r = client.get(
        f"/artifact_schemas/{ARTIFACT_SCHEMA_ID}",
        headers={"Authorization": f"Bearer {login}"},
    )
    acc = ArtifactSchema(**r.json())

    r = client.delete(
        f"/artifact_schemas/{ARTIFACT_SCHEMA_ID}",
        headers={"Authorization": f"Bearer {login}"},
    )

    assert r.status_code == 200
    assert acc == ArtifactSchema(**r.json())

    # a get returns null
    r = client.get(
        f"/artifact_schemas/{ARTIFACT_SCHEMA_ID}",
        headers={"Authorization": f"Bearer {login}"},
    )
    assert r.json() is None

    # a second delete return null
    r = client.delete(
        f"/artifact_schemas/{ARTIFACT_SCHEMA_ID}",
        headers={"Authorization": f"Bearer {login}"},
    )
    assert r.json() is None

    # recreate artifact_schema for other tests
    test_create_artifact_schema(login)
