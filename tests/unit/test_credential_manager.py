"""docs/security/05-DATA-PROTECTION.md §1, docs/phase-7/
CREDENTIAL-MANAGEMENT.md — CredentialManager/FileCredentialStore never
stores a raw secret in plaintext."""

from __future__ import annotations

import json

import pytest
from app.services.credential_manager import (
    CredentialManager,
    FileCredentialStore,
    WindowsDPAPICredentialStore,
)


@pytest.fixture
def store(tmp_path):
    return FileCredentialStore(secret_key="test-secret-key", path=tmp_path / "creds.enc.json")


@pytest.fixture
def manager(store):
    return CredentialManager(store)


def test_store_then_retrieve_round_trips(manager):
    ref = manager.store_credential("super-secret-token")
    assert manager.retrieve_credential(ref) == "super-secret-token"


def test_ref_is_opaque_and_unique(manager):
    ref1 = manager.store_credential("secret-one")
    ref2 = manager.store_credential("secret-two")
    assert ref1 != ref2
    assert "secret-one" not in ref1
    assert "secret-two" not in ref2


def test_unknown_ref_returns_none(manager):
    assert manager.retrieve_credential("cred_does_not_exist") is None


def test_delete_removes_the_credential(manager):
    ref = manager.store_credential("to-be-deleted")
    manager.delete_credential(ref)
    assert manager.retrieve_credential(ref) is None


def test_deleting_unknown_ref_is_a_harmless_noop(manager):
    manager.delete_credential("cred_does_not_exist")  # must not raise


def test_rotate_keeps_the_same_ref_with_a_new_secret(manager):
    ref = manager.store_credential("old-secret")
    manager.rotate_credential(ref, "new-secret")
    assert manager.retrieve_credential(ref) == "new-secret"


def test_validate_credential(manager):
    ref = manager.store_credential("valid")
    assert manager.validate_credential(ref) is True
    manager.delete_credential(ref)
    assert manager.validate_credential(ref) is False


def test_file_on_disk_never_contains_the_plaintext_secret(store, tmp_path):
    store.store("cred_x", "extremely-secret-value")
    on_disk = (tmp_path / "creds.enc.json").read_text()
    assert "extremely-secret-value" not in on_disk
    # Sanity: it's real JSON with an opaque ciphertext value, not just an
    # unreadable blob that happens to also not contain the substring.
    parsed = json.loads(on_disk)
    assert parsed["cred_x"] != "extremely-secret-value"


def test_wrong_secret_key_cannot_decrypt(tmp_path):
    original = FileCredentialStore(secret_key="key-one", path=tmp_path / "creds.enc.json")
    original.store("cred_x", "secret-value")

    wrong_key = FileCredentialStore(secret_key="key-two", path=tmp_path / "creds.enc.json")
    assert wrong_key.retrieve("cred_x") is None


def test_same_secret_key_decrypts_across_separate_store_instances(tmp_path):
    """A restart creates a new FileCredentialStore instance against the
    same file and secret_key — must still decrypt what a previous
    instance wrote."""
    path = tmp_path / "creds.enc.json"
    FileCredentialStore(secret_key="stable-key", path=path).store("cred_x", "persisted")
    reloaded = FileCredentialStore(secret_key="stable-key", path=path)
    assert reloaded.retrieve("cred_x") == "persisted"


def test_corrupted_file_is_treated_as_empty_not_a_crash(tmp_path):
    path = tmp_path / "creds.enc.json"
    path.write_text("not valid json {{{")
    store = FileCredentialStore(secret_key="k", path=path)
    assert store.retrieve("cred_x") is None


def test_windows_dpapi_store_is_a_documented_extension_point_not_implemented():
    with pytest.raises(NotImplementedError):
        WindowsDPAPICredentialStore()
