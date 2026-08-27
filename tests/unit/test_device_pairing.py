"""docs/phase-7/DEVICE-PAIRING.md — DevicePairingService enforces
CLAUDE.md's six-stage device flow with no stage skippable, in isolation
from the HTTP layer."""

from __future__ import annotations

import pytest
from app.services.credential_manager import CredentialManager, FileCredentialStore
from app.services.device_pairing import (
    DevicePairingService,
    PairingStageError,
    UnknownDeviceError,
    UnregisteredCapabilityError,
)
from veyra_contracts import ConnectionProtocol, DeviceType


@pytest.fixture
def service(tmp_path) -> DevicePairingService:
    cm = CredentialManager(FileCredentialStore(secret_key="k", path=tmp_path / "c.enc.json"))
    return DevicePairingService(cm)


async def _paired(service, db_session, name="AC"):
    return await service.pair(
        db_session, name=name, device_type=DeviceType.AC, protocol=ConnectionProtocol.LOCAL_HTTP
    )


async def test_pair_starts_unpaired_at_stage_pair(service, db_session):
    row = await _paired(service, db_session)
    assert row.trust_status.value == "UNPAIRED"
    assert row.pairing_stage.value == "PAIR"


async def test_identify_then_authenticate_then_authorize_then_register(service, db_session):
    row = await _paired(service, db_session)
    row = await service.identify(db_session, row.id)
    assert row.pairing_stage.value == "IDENTIFY"
    assert row.trust_status.value == "PAIRING"

    row = await service.authenticate(db_session, row.id, secret="shared-secret")
    assert row.pairing_stage.value == "AUTHENTICATE"
    assert row.credentials_ref is not None

    row = await service.authorize(db_session, row.id)
    assert row.pairing_stage.value == "AUTHORIZE"

    row = await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    assert row.pairing_stage.value == "REGISTER_CAPABILITIES"
    assert row.trust_status.value == "PAIRED"


@pytest.mark.parametrize(
    "method_name, kwargs",
    [
        # identify() is the one legitimate next step from PAIR — not
        # included here as a "must reject" case, see the test below it.
        ("authenticate", {"secret": "x"}),
        ("authorize", {}),
        ("register_capabilities", {"capability_keys": ["power"]}),
    ],
)
async def test_every_later_stage_rejects_being_reached_directly_from_pair(
    service, db_session, method_name, kwargs
):
    """A freshly-paired device (stage PAIR) must reject every stage
    except the immediate next one (identify)."""
    row = await _paired(service, db_session)
    method = getattr(service, method_name)
    with pytest.raises(PairingStageError):
        await method(db_session, row.id, **kwargs)


async def test_identify_is_the_one_legitimate_next_step_from_pair(service, db_session):
    row = await _paired(service, db_session)
    row = await service.identify(db_session, row.id)
    assert row.pairing_stage.value == "IDENTIFY"


async def test_cannot_grant_permission_before_register_capabilities(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    with pytest.raises(PairingStageError):
        await service.grant_permission(db_session, row.id, capability_key="power")


async def test_cannot_grant_an_unregistered_capability(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    with pytest.raises(UnregisteredCapabilityError):
        await service.grant_permission(db_session, row.id, capability_key="temperature")


async def test_is_permission_valid_false_until_granted_true_after(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])

    assert service.is_permission_valid(row.id, "power") is False
    await service.grant_permission(db_session, row.id, capability_key="power")
    assert service.is_permission_valid(row.id, "power") is True


async def test_revoke_makes_permission_invalid_again(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    await service.grant_permission(db_session, row.id, capability_key="power")

    await service.revoke_permission(db_session, row.id, capability_key="power")
    assert service.is_permission_valid(row.id, "power") is False


async def test_unknown_device_raises_lookup_error(service, db_session):
    with pytest.raises(UnknownDeviceError):
        await service.identify(db_session, "does-not-exist")


async def test_reset_permission_cache_clears_all_grants(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    await service.grant_permission(db_session, row.id, capability_key="power")

    service.reset_permission_cache()
    assert service.is_permission_valid(row.id, "power") is False


async def test_rebuild_permission_cache_on_startup_restores_a_real_grant(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    await service.grant_permission(db_session, row.id, capability_key="power")

    service.reset_permission_cache()  # simulate a process restart
    await service.rebuild_permission_cache_on_startup(db_session)
    assert service.is_permission_valid(row.id, "power") is True


async def test_rebuild_permission_cache_on_startup_skips_revoked_grants(service, db_session):
    row = await _paired(service, db_session)
    await service.identify(db_session, row.id)
    await service.authenticate(db_session, row.id, secret="s")
    await service.authorize(db_session, row.id)
    await service.register_capabilities(db_session, row.id, capability_keys=["power"])
    await service.grant_permission(db_session, row.id, capability_key="power")
    await service.revoke_permission(db_session, row.id, capability_key="power")

    service.reset_permission_cache()
    await service.rebuild_permission_cache_on_startup(db_session)
    assert service.is_permission_valid(row.id, "power") is False
