"""
04 - One-to-one transfer + progress monitoring
=============================================

The core flow: create an immediate transfer between two registered devices,
then poll its status until it reaches a terminal state. Status is an integer
code (see innorix.TRANSFER_STATUS); percent is 0-100.

Endpoints:
  POST /api/transfer/manualTransfer
  GET  /api/transfer/{monitorId}/detail-unified

Run:
  python examples/04_transfer_manual.py
"""

from _common import make_client
from innorix import status_name


def main() -> None:
    client, settings = make_client()

    # Guard: both devices should be online, otherwise the transfer may stall.
    for role, device_id in (("source", settings.source_id),
                            ("target", settings.target_id)):
        if not client.is_online(device_id):
            raise SystemExit(f"{role} device is offline: {device_id}")

    monitor_id = client.create_transfer(
        source_id=settings.source_id,
        target_id=settings.target_id,
        target_path=settings.target_path,
        source_file_paths=settings.source_paths,
    )
    print("monitorId:", monitor_id)

    final = client.wait_for_completion(monitor_id, interval=3.0)
    print(f"final status: {final} ({status_name(final)})")


if __name__ == "__main__":
    main()
