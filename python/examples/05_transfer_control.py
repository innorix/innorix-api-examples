"""
05 - Transfer control & retry
============================

Pause, resume, and cancel an in-flight transfer, and retry only the files that
failed. Control actions are PATCH requests with no body.

Timing note: pause/resume are asynchronous. After you request a pause, the
agent needs a moment to actually stop and for the server to settle the state.
Sending "resume" too early returns:
    400 "Transfer is already PAUSE_OR_CANCEL cannot excute command"
So instead of a fixed sleep we poll until the state settles, then resume with a
small retry.

Endpoints:
  PATCH /api/transfer/pause/{monitorId}
  PATCH /api/transfer/resume/{monitorId}
  PATCH /api/transfer/cancel/{monitorId}
  POST  /api/transfer/retry-failed-files

Run:
  python examples/05_transfer_control.py
"""

import time
from _common import make_client
from innorix import status_name, TERMINAL_STATES

TRANSFERRING = 6
PAUSE = 3
RESUMABLE_AFTER_PAUSE = {3}  # server considers pause settled once status == 3


def wait_until(client, monitor_id, target_states, timeout=30.0, interval=1.5):
    """Poll until status is in target_states (or a terminal state) or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get_status(monitor_id)
        if status in target_states or status in TERMINAL_STATES:
            return status
        time.sleep(interval)
    return client.get_status(monitor_id)


def resume_with_retry(client, monitor_id, attempts=5, delay=1.5):
    """Resume, retrying while the server still reports the pause isn't settled."""
    for i in range(attempts):
        try:
            client.control(monitor_id, "resume")
            return True
        except Exception as exc:  # ApiError from a 400 while state is settling
            if i == attempts - 1:
                raise
            print(f"resume not ready yet ({exc}); retrying...")
            time.sleep(delay)
    return False


def main() -> None:
    client, settings = make_client()

    # Start a transfer to control.
    monitor_id = client.create_transfer(
        source_id=settings.source_id,
        target_id=settings.target_id,
        target_path=settings.target_path,
        source_file_paths=settings.source_paths,
    )
    print("monitorId:", monitor_id)

    # Wait until the transfer is actually running before pausing. Sending pause
    # too early (before it reaches transferring=6) has no effect.
    running = wait_until(client, monitor_id, {TRANSFERRING})
    print("status before pause:", status_name(running))

    if running in TERMINAL_STATES:
        print("transfer finished before it could be paused (too small/fast)")
        return

    client.control(monitor_id, "pause")

    # Wait until the pause has actually settled before resuming.
    settled = wait_until(client, monitor_id, RESUMABLE_AFTER_PAUSE)
    print("status after pause:", status_name(settled))

    if settled in TERMINAL_STATES:
        print("transfer already finished; nothing to resume")
    else:
        resume_with_retry(client, monitor_id)

        # To cancel instead of resuming:
        # client.control(monitor_id, "cancel")

        final = client.wait_for_completion(monitor_id, interval=3.0)
        print(f"final status: {final} ({status_name(final)})")

        # If the transfer partially failed (status 9), retry just the failed files.
        if final == 9:
            client.retry_failed(monitor_id, [
                {"filePath": "C:/data/export/file.txt", "isFolder": False},
            ])


if __name__ == "__main__":
    main()
