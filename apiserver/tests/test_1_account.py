from fastapi.testclient import TestClient
from worst_crm.main import app
from worst_crm.models import Account, AccountOverview
from worst_crm.tests import utils
from worst_crm.tests.utils import login, setup_test
import hashlib
import validators
from faker import Faker

fake = Faker()

client = TestClient(app)

ACCOUNT_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_get_accounts_non_auth(setup_test):
    r = client.get("/accounts")

    assert r.status_code == 401


def test_create_account(login, setup_test):
    r = client.post(
        "/accounts",
        headers={"Authorization": f"Bearer {login}"},
        json={
            "name": "ACC-1",
            "account_id": ACCOUNT_ID,
            "text": "Initial text",
            "status": "NEW",
            "owned_by": "dummyadmin",
            "tags": ["t1", "t2", "t1"],
        },
    )

    assert r.status_code == 200
    acc = Account(**r.json())
    assert isinstance(acc, Account)


def test_load_accounts(login, setup_test):
    for _ in range(100):
        r = client.post(
            "/accounts",
            headers={"Authorization": f"Bearer {login}"},
            json={
                "name": fake.company(),
                "text": fake.text(),
                "status": "NEW",
                "owned_by": "dummyadmin",
                "tags": ["t1", "t2", "t1"],
            },
        )


def test_update_account(login, setup_test):
    r = client.put(
        f"/accounts",
        headers={"Authorization": f"Bearer {login}"},
        json={
            "name": "ACC-1",
            "account_id": ACCOUNT_ID,
            "text": "I've updated this text",
            "status": "OPPORTUNITY",
            "owned_by": "dummyadmin",
        },
    )
    assert r.status_code == 200
    upd_acc = Account(**r.json())

    # fetch stored account
    r = client.get(
        f"/accounts/{ACCOUNT_ID}", headers={"Authorization": f"Bearer {login}"}
    )

    assert r.status_code == 200
    acc = Account(**r.json())

    assert upd_acc == acc
    assert acc.text == "I've updated this text"


def test_get_all_accounts(login, setup_test):
    r = client.get(
        "/accounts",
        headers={"Authorization": f"Bearer {login}"},
    )

    l: list[AccountOverview] = [AccountOverview(**x) for x in r.json()]

    assert r.status_code == 200
    assert len(l) >= 100


def test_get_all_accounts_with_filters(login, setup_test):
    r = client.request(
        "GET",
        "/accounts",
        headers={"Authorization": f"Bearer {login}"},
        json={
            "name": ["ACC-1"],
        },
    )

    assert r.status_code == 200
    l: list[AccountOverview] = [AccountOverview(**x) for x in r.json()]
    assert len(l) == 1


def test_attachment_upload_and_download(login, setup_test):
    for filename in ["1MB with spaces.txt", "ss.png"]:
        # uploading
        r = client.get(
            f"/accounts/{ACCOUNT_ID}/presigned-put-url/{filename}",
            headers={"Authorization": f"Bearer {login}"},
        )

        assert r.status_code == 200

        assert validators.url(r.text)  # type: ignore

        utils.s3_upload(r.text, f".testdata/{filename}")

        # Downloading
        r = client.get(
            f"/accounts/{ACCOUNT_ID}/presigned-get-url/{filename}",
            headers={"Authorization": f"Bearer {login}"},
        )

        assert r.status_code == 200

        assert validators.url(r.text)  # type: ignore

        utils.s3_download(r.text, f".testdata/.{filename}")

        # comparing for equality
        with open(f".testdata/{filename}", "rb") as f:
            digest1 = hashlib.file_digest(f, "sha256")

        with open(f".testdata/.{filename}", "rb") as f:
            digest2 = hashlib.file_digest(f, "sha256")  # type: ignore

        assert digest1.hexdigest() == digest2.hexdigest()

        # deleting attachment
        r = client.delete(
            f"accounts/{ACCOUNT_ID}/attachments/{filename}",
            headers={"Authorization": f"Bearer {login}"},
        )

        assert r.status_code == 200

        # deleting attachment twice
        r = client.delete(
            f"accounts/{ACCOUNT_ID}/attachments/{filename}",
            headers={"Authorization": f"Bearer {login}"},
        )

        assert r.status_code == 200


def test_delete_account(login):
    r = client.get(
        f"/accounts/{ACCOUNT_ID}", headers={"Authorization": f"Bearer {login}"}
    )
    acc = Account(**r.json())

    r = client.delete(
        f"/accounts/{ACCOUNT_ID}", headers={"Authorization": f"Bearer {login}"}
    )

    assert r.status_code == 200
    assert acc == Account(**r.json())

    # a get returns null
    r = client.get(
        f"/accounts/{ACCOUNT_ID}", headers={"Authorization": f"Bearer {login}"}
    )
    assert r.json() is None

    # a second delete return null
    r = client.delete(
        f"/accounts/{ACCOUNT_ID}", headers={"Authorization": f"Bearer {login}"}
    )
    assert r.json() is None

    # recreate account for other tests
    test_create_account(login, setup_test)
