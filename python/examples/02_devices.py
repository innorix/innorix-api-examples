"""
02 - Devices & connectivity
==========================

List registered devices, find the source/target deviceId, and check whether
each device is online before you attempt a transfer.

Endpoints:
  GET /api/device
  GET /api/device/connectivity/{deviceId}
  GET /api/device/{device_id}/detail

Run:
  python examples/02_devices.py
"""

from _common import make_client


def main() -> None:
    client, settings = make_client()

    devices = client.list_devices()
    print(f"{len(devices)} device(s) registered:")
    for d in devices:
        name = d.get("deviceName") or d.get("name")
        device_id = d.get("deviceId") or d.get("id")
        print(f"  - {name}  ({device_id})")

    # Check connectivity of the configured source/target devices.
    for role, device_id in (("source", settings.source_id),
                            ("target", settings.target_id)):
        online = client.is_online(device_id)
        print(f"{role} {device_id} online={online}")

    # Full detail of one device (uncomment to inspect):
    # import json
    # print(json.dumps(client.device_detail(settings.source_id), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
