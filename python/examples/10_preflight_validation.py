"""
10 - Pre-flight validation
=========================

Reduce transfer failures by validating up front: check the target path, measure
how many files / how much data a path holds, and screen files against the
workspace security policy before sending.

Endpoints:
  POST /api/transfer/validation/path
  GET  /api/device/total-file-and-size-on-path/{deviceId}
  POST /api/security-policy/check-transfer-valid

Run:
  python examples/10_preflight_validation.py
"""

import json
from _common import make_client


def main() -> None:
    client, settings = make_client()

    # 1) Validate that the source/target and target path are usable.
    path_check = client.validate_path(
        source_id=settings.source_id,
        target_id=settings.target_id,
        target_path=settings.target_path,
    )
    print("path validation:")
    print(json.dumps(path_check, indent=2, ensure_ascii=False)[:600])

    # 2) How big is what we are about to send?
    size_info = client.total_file_and_size(settings.source_id, settings.source_paths[0])
    print("total file/size:")
    print(json.dumps(size_info, indent=2, ensure_ascii=False)[:600])

    # 3) Screen the files against the security policy (sensitive extensions, etc.).
    sender_files = [
        {"name": "report.pdf", "filePath": f"{settings.source_paths[0]}/report.pdf", "type": "file"},
    ]
    policy = client.check_transfer_valid(
        source_id=settings.source_id,
        target_id=settings.target_id,
        sender_files=sender_files,
    )
    print("security policy check:")
    print(json.dumps(policy, indent=2, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
