# Device Gateway

DeviceGatewayAdapter implementations (Matter/MQTT/local HTTP/Bluetooth/vendor APIs). See docs/architecture/10-IOT.md.

The interface a future adapter implements now exists:
`services/local-api/app/services/device_adapter.py`'s `DeviceAdapter`
Protocol (subsystem activation, docs/subsystem-activation/IOT-STATUS.md).
No concrete adapter ships yet — pairing/identity/authorization are already
real in `app/services/device_pairing.py`; a `DeviceAdapter` is the next
stage after CONTROL is authorized, and does not exist for any real
protocol yet. Do not add a fake/stub adapter here to make this directory
look more complete than it is — the deny-by-default device trust model
has nothing real to connect to until a genuine protocol implementation
lands in a future phase.
