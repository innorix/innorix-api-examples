"""
07 - Scheduled automation (recurring transfers)
==============================================

Create an automation (a saved/scheduled transfer), then list, inspect, pause,
update, and delete it.

Payload shape (mirrors what the web app sends):

  {
    "name": "...",
    "flowId": "<uuid>",
    "transferType": "no_schedule" | "schedule",
    "timezone": "Asia/Seoul",
    "callbackURL": null,
    "schedules": [{ "type": "none", "hour": "01", "minute": "00", ... }],
    "details": [{
      "automationDetailId": "",          # empty on create
      "senderId": "<source deviceId>",
      "receiverId": "<target deviceId>",
      "step": 1,
      "fileCount": 1, "folderCount": 0, "sizeCount": 15872,
      "sourceItem": [{
        "hash": "<senderId>_ino_<base64url(path)>",
        "isDir": false,
        "fileSize": 15872
      }],
      "targetPath": "<receiverId>_ino_<base64url(path)>",
      "transferOptions": {"sendFileOption": {}, "targetAction": "numbering"}
    }]
  }

Both sourceItem[].hash and targetPath are device-scoped path references:
  {deviceId}_ino_{base64url(path)}   (see innorix.encode_path_ref)

Endpoints:
  POST   /api/automation
  GET    /api/automation
  GET    /api/automation/{automationId}/details
  POST   /api/automation/pause
  PATCH  /api/automation/{automationId}
  DELETE /api/automation/{automationId}

Run:
  python examples/07_automation.py
"""

import json
import uuid
from datetime import datetime, timezone

from _common import make_client
from innorix import encode_path_ref


def build_source_item(sender_id: str, path: str, is_dir: bool, file_size: int) -> dict:
    """One entry of details[].sourceItem."""
    return {
        "hash": encode_path_ref(sender_id, path),
        "isDir": is_dir,
        "fileSize": file_size,
    }


def resolve_size(client, device_id: str, path: str) -> tuple[int, int]:
    """
    Return (total_size, total_files) for a path on the device via
    GET /api/device/total-file-and-size-on-path/{deviceId}.
    Falls back to (0, 0) if the lookup fails so the example still runs.
    """
    try:
        resp = client.total_file_and_size(device_id, path)
        data = resp.get("data", resp) if isinstance(resp, dict) else {}
        return int(data.get("totalSize", 0)), int(data.get("totalFiles", 0))
    except Exception as exc:
        print(f"warning: size lookup failed for {path}: {exc}")
        return 0, 0


def main() -> None:
    client, settings = make_client()

    # --- Build the source items from .env paths. -------------------------- #
    # Paths and their isDir flags come from INNORIX_SOURCE_PATHS /
    # INNORIX_SOURCE_IS_DIR; file sizes/counts are fetched from the device.
    source_item = []
    file_count = 0
    folder_count = 0
    size_count = 0

    for path, is_dir in zip(settings.source_paths, settings.source_is_dir):
        total_size, total_files = resolve_size(client, settings.source_id, path)
        source_item.append(
            build_source_item(settings.source_id, path, is_dir, total_size)
        )
        size_count += total_size
        if is_dir:
            folder_count += 1
            file_count += total_files          # files contained in the folder
        else:
            file_count += 1

    detail = {
        "automationDetailId": "",            # empty string on create
        "sourceItem": source_item,
        "targetPath": encode_path_ref(settings.target_id, settings.target_path),
        "senderId": settings.source_id,
        "receiverId": settings.target_id,
        "step": 1,
        "fileCount": file_count,
        "folderCount": folder_count,
        "sizeCount": size_count,
        "transferOptions": {"sendFileOption": {}, "targetAction": "numbering"},
    }

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    payload = {
        "name": "Transfer via API example",
        "flowId": str(uuid.uuid4()),
        "details": [detail],
        # "no_schedule" runs once with no recurring timetable.
        # For a recurring job use "schedule" and fill schedules[0] accordingly.
        "transferType": "no_schedule",
        "timezone": "Asia/Seoul",
        "callbackURL": None,
        "schedules": [{
            "type": "none",              # e.g. "day" / "week" / "month" when scheduling
            "hour": "01",
            "minute": "00",
            "ampm": "am",
            "dayInMonth": 1,
            "dayInWeek": "monday",
            "startDate": now_iso,
            "timezone": "Asia/Seoul",
        }],
    }

    created = client.create_automation(payload)
    print(json.dumps(created, indent=2, ensure_ascii=False))

    automation_id = (created.get("data") or {}).get("automationId") \
        or created.get("automationId")
    print("automationId:", automation_id)

    # List automations.
    client.list_automations()

    # Inspect / manage this automation.
    if automation_id:
        client.automation_details(automation_id)
        # client.pause_automation(True)
        # client.update_automation(automation_id, {"name": "renamed"})
        # client.delete_automation(automation_id)


if __name__ == "__main__":
    main()
