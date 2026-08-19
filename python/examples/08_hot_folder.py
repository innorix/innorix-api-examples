"""
08 - Hot folders
===============

A hot folder watches a directory on a device so that files placed there are
picked up automatically. This example registers a hot folder, lists them, and
updates/deletes one.

Endpoints:
  POST   /api/hot-folder
  GET    /api/hot-folder
  GET    /api/hot-folder/{id}
  PATCH  /api/hot-folder/{id}
  DELETE /api/hot-folder/{id}

Run:
  python examples/08_hot_folder.py
"""

import json
from _common import make_client


def main() -> None:
    client, settings = make_client()

    # Create a hot folder on the source device.
    created = client.create_hot_folder(
        device_id=settings.source_id,
        path=settings.source_paths[0],
    )
    print(json.dumps(created, indent=2, ensure_ascii=False))

    # List existing hot folders.
    folders = client.list_hot_folders()
    print(json.dumps(folders, indent=2, ensure_ascii=False)[:1000])

    # Update / delete a specific hot folder by its UUID:
    # hot_folder_id = "<HOT_FOLDER_ID>"
    # client.get_hot_folder(hot_folder_id)
    # client.update_hot_folder(hot_folder_id, {"path": "C:/data/new_watch"})
    # client.delete_hot_folder(hot_folder_id)


if __name__ == "__main__":
    main()
