"""
03 - Remote file explorer
========================

Browse a source device's filesystem and manage folders remotely: create,
rename, and delete. Useful when you need to discover the exact file paths to
transfer instead of hard-coding them.

Endpoints:
  POST /api/explorer/fileSearchV3/{deviceId}
  POST /api/explorer/createFolder/{deviceId}
  POST /api/explorer/renameFile/{deviceId}
  POST /api/explorer/removeFile/{deviceId}

Run:
  python examples/03_explorer.py
"""

import json
from _common import make_client


def main() -> None:
    client, settings = make_client()
    device_id = settings.source_id
    base = settings.source_paths[0]

    # 1) Browse a path (set only_folder=True to list folders only).
    listing = client.browse(device_id, base, only_folder=False)
    print(json.dumps(listing, indent=2, ensure_ascii=False)[:1000])

    # --- The mutating calls below are commented out on purpose. -------------
    # Uncomment and adjust paths to actually create/rename/delete on the device.

    # 2) Create a folder.
    # client.create_folder(device_id, f"{base}/example_new_folder")

    # 3) Rename it (path = current path, name = new leaf name).
    # client.rename_file(device_id, f"{base}/example_new_folder", "renamed_folder")

    # 4) Remove files/folders (listFiles = absolute paths).
    # client.remove_files(device_id, [f"{base}/renamed_folder"])


if __name__ == "__main__":
    main()
