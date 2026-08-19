"""
06 - Replay a previous transfer
==============================

The replay endpoint has two actions, both shown below:
  action='review' -> return the original transfer's configuration (read-only)
  action='replay' -> start a NEW transfer using that same configuration

A typical flow is: review first to confirm what will be sent, then replay.

Endpoints:
  POST /api/transfer/{monitorId}/replay

Run:
  MONITOR_ID=<previous_monitor_id> python examples/06_transfer_replay.py
"""

import os
import json
from _common import make_client


def main() -> None:
    client, settings = make_client()

    monitor_id = os.getenv("MONITOR_ID", "<PREVIOUS_MONITOR_ID>")

    # 1) review: inspect the configuration of the original transfer (no side effect).
    config = client.replay(monitor_id, action="review")
    print("[review] original transfer configuration:")
    print(json.dumps(config, indent=2, ensure_ascii=False)[:1000])

    # 2) replay: start a new transfer with that configuration.
    #    This has a side effect (creates a new transfer), so it is opt-in.
    #    Note: the replay response only reports success (data: true); it does
    #    NOT return the new monitorId. To monitor the resulting transfer, look
    #    it up afterwards via the source device's transfer list, e.g.
    #    GET /api/transfer/unified-by-device.
    if os.getenv("DO_REPLAY") == "1":
        result = client.replay(monitor_id, action="replay")
        print("[replay] result:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        ok = bool(result.get("data")) if isinstance(result, dict) else False
        print("replay started successfully" if ok else "replay did not succeed")
    else:
        print("\n(set DO_REPLAY=1 to actually replay and start a new transfer)")


if __name__ == "__main__":
    main()
