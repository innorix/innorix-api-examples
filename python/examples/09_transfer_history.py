"""
09 - Transfer history & CSV report
=================================

Look up the detail and per-file results of a completed transfer, and export the
whole history as CSV for auditing/reporting.

Endpoints:
  GET /api/transfer-history/{id}/detail?idType=monitor
  GET /api/transfer-history/{id}/get-files?idType=monitor
  GET /api/transfer-history/export-csv

Run:
  MONITOR_ID=<monitor_id> python examples/09_transfer_history.py
"""

import os
import json
from _common import make_client


def main() -> None:
    client, settings = make_client()

    monitor_id = os.getenv("MONITOR_ID", "<MONITOR_ID>")

    # Summary of a completed transfer (idType=monitor because we pass a monitorId).
    detail = client.history_detail(monitor_id, id_type="monitor")
    print(json.dumps(detail, indent=2, ensure_ascii=False)[:1000])

    # Per-file results.
    files = client.history_files(monitor_id, id_type="monitor", page=1, size=20)
    print(json.dumps(files, indent=2, ensure_ascii=False)[:1000])

    # Export history as CSV.
    out = client.export_history_csv("transfer_history.csv", page=1, size=50,
                                    sort="createdAt:desc")
    print("saved:", out)


if __name__ == "__main__":
    main()
