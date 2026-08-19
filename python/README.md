# Innorix API Examples — Python

Runnable Python examples for the Innorix file-transfer API. They cover the
common developer flows end to end: authentication, device discovery, one-to-one
transfers, transfer control, scheduled automations, hot folders,
history/reporting, and pre-flight validation.

The authoritative endpoint reference is the OpenAPI document in
[`../openapi/innorix-openapi.yaml`](../openapi/innorix-openapi.yaml)
(also browsable as Swagger UI on the API host).

## Two ways to read the same examples

This folder ships each example in **two forms**:

- **`examples/`** — the maintained source. Thin scripts that import a shared
  client from the `innorix/` package. This is where edits happen.
- **`standalone/`** — a self-contained copy of each example (client code inlined
  into a single file). Handy for the website's "view source", or for copying one
  file into your own project without pulling in the package.

The two are kept in sync (see [Keeping standalone in sync](#keeping-standalone-in-sync)).
Pick whichever fits: learning the package once, or grabbing a single file.

## Requirements

- Python 3.9+
- `requests` (required), `python-dotenv` (optional, for `.env` loading)

```bash
pip install -r requirements.txt
```

## Quick start

```bash
cd python
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then edit .env with your own values

# Run the package version…
python examples/01_auth.py
# …or the self-contained version:
python standalone/01_auth.py
```

Configuration is read from `.env` (or environment variables), so you set your
credentials and device IDs once. **Never commit your real `.env`** — it is
git-ignored.

## Project layout

```
python/
├── innorix/                 # shared client package (import this in your own code)
│   ├── __init__.py
│   ├── client.py            # InnorixClient + transfer status helpers + path-ref helpers
│   └── config.py            # loads settings from .env / environment
├── examples/                # maintained source — thin scripts using the package
│   ├── _common.py           # shared bootstrap: logging + logged-in client
│   └── 01_auth.py … 10_preflight_validation.py
├── standalone/              # generated — one self-contained file per example
│   └── 01_auth.py … 10_preflight_validation.py
├── tools/
│   └── build_standalone.py  # regenerates standalone/ from examples/ + innorix/
├── requirements.txt
├── .env.example
└── README.md
```

## Examples

Each example is small, focused, and safe to run first (mutating calls like
create/delete are commented out and clearly marked).

### 01 · Authentication — `01_auth.py`
Logs in, sets the auth headers, and fetches the current user. Also shows how to
refresh an expired token. **Start here** — every other example reuses this login
step. *Endpoints: `POST /api/auth/login`, `GET /api/auth/me`,
`POST /api/auth/refresh-token`, `GET /api/auth/logout`.*

### 02 · Devices & connectivity — `02_devices.py`
Lists the devices registered in your workspace and checks whether the
source/target devices are online. Use it to find the `deviceId` values the
transfer examples need, and to guard against sending to an offline device.
*Endpoints: `GET /api/device`, `GET /api/device/connectivity/{deviceId}`,
`GET /api/device/{deviceId}/detail`.*

### 03 · Remote file explorer — `03_explorer.py`
Browses a device's filesystem and manages folders remotely (create, rename,
delete). Use it to discover exact file paths before a transfer instead of
hard-coding them. *Endpoints: `POST /api/explorer/fileSearchV3/{deviceId}`
(+ `createFolder` / `renameFile` / `removeFile`).*

### 04 · One-to-one transfer + monitoring — `04_transfer_manual.py`
The core flow: create an immediate transfer between two devices, then poll until
it finishes. Status is an integer code and `percent` is 0–100. This is the
example most people come for. *Endpoints: `POST /api/transfer/manualTransfer`,
`GET /api/transfer/{monitorId}/detail-unified`.*

### 05 · Transfer control & retry — `05_transfer_control.py`
Pause, resume, and cancel a running transfer, and retry only the files that
failed. Because pause/resume are asynchronous, it waits for the transfer to be
`transferring` before pausing and for the pause to settle before resuming (with
a small retry). *Endpoints: `PATCH /api/transfer/{pause|resume|cancel}/{monitorId}`,
`POST /api/transfer/retry-failed-files`.*

### 06 · Replay a previous transfer — `06_transfer_replay.py`
Re-runs a past transfer by `monitorId`. `action="review"` returns the original
configuration (read-only); `action="replay"` starts a new transfer with it. The
replay response reports success only, not a new `monitorId`. *Endpoint:
`POST /api/transfer/{monitorId}/replay`.*

### 07 · Scheduled automation — `07_automation.py`
Creates a saved/scheduled transfer (an "automation"), then lists and inspects
it. Automations use device-scoped **encoded path references**
(`{deviceId}_ino_{base64url(path)}`) and per-item metadata; file sizes are
fetched from the device automatically. *Endpoints: `POST /api/automation`,
`GET /api/automation`, `GET /api/automation/{automationId}/details`
(+ `pause` / update / delete).*

### 08 · Hot folders — `08_hot_folder.py`
Registers a "hot folder" that watches a directory so files dropped there are
transferred automatically, then lists them. Shows update/delete too.
*Endpoints: `POST /api/hot-folder`, `GET /api/hot-folder`,
`GET|PATCH|DELETE /api/hot-folder/{id}`.*

### 09 · Transfer history & CSV report — `09_transfer_history.py`
Looks up the summary and per-file results of a completed transfer and exports
the history as CSV for auditing/reporting. *Endpoints:
`GET /api/transfer-history/{id}/detail`, `.../get-files`, `.../export-csv`.*

### 10 · Pre-flight validation — `10_preflight_validation.py`
Reduces failures by validating before you send: checks the target path, measures
file count/size on a path, and screens files against the workspace security
policy. *Endpoints: `POST /api/transfer/validation/path`,
`GET /api/device/total-file-and-size-on-path/{deviceId}`,
`POST /api/security-policy/check-transfer-valid`.*

Some examples (06, 09) take a `MONITOR_ID` from a previous transfer:

```bash
MONITOR_ID=<monitor_id> python examples/09_transfer_history.py
```

## Transfer status codes

`GET /api/transfer/{monitorId}/detail-unified` returns `status` as an integer.
The full mapping lives in `innorix.TRANSFER_STATUS`; the terminal states are:

| Code | Name | Meaning |
|------|------|---------|
| 2 | `transferComplete` | Completed |
| 4 | `transferError` | Error |
| 5 | `transferCancel` | Cancelled |
| 9 | `transferPartialComplete` | Some files failed |
| 99 | `transferFail` | Failed |

`wait_for_completion()` stops on any of these. `transferring` is `6`;
`transferPause` is `3` (resumable, so not terminal).

## Encoded path references

The automation API (07) does not take plain paths. Each `sourceItem[].hash` and
`targetPath` is a device-scoped reference:

```
{deviceId}_ino_{base64url(path)}
```

Use `innorix.encode_path_ref(device_id, path)` / `decode_path_ref(ref)` to build
and read them. Source items are scoped to the sender device, `targetPath` to the
receiver.

## Configuration

All values come from environment variables (or `.env`); see `.env.example`.

| Variable | Purpose |
|----------|---------|
| `INNORIX_BASE_URL` | API base URL |
| `INNORIX_WORKSPACE_ID` | Workspace ID (sent as `x-workspace-id`) |
| `INNORIX_EMAIL` / `INNORIX_PASSWORD` | Login credentials |
| `INNORIX_SOURCE_ID` / `INNORIX_TARGET_ID` | Source/target device IDs |
| `INNORIX_TARGET_PATH` | Save path on the target device |
| `INNORIX_SOURCE_PATHS` | Source paths (comma-separated) |
| `INNORIX_SOURCE_IS_DIR` | Per-path directory flags for example 07 (comma-separated true/false) |

## Keeping standalone in sync

`standalone/` is generated from `examples/` + `innorix/`, not edited by hand.
After changing the shared client or an example, regenerate:

```bash
python tools/build_standalone.py
```

CI verifies that `standalone/` compiles and contains no package imports, so the
two forms can't silently drift.

## Notes

- Use forward slashes in Windows paths (e.g. `C:/Users/...`).
- `sourceItem` paths are **source-device-absolute**; `targetPath` is
  **target-device-absolute**.
- Mutating calls (create/rename/delete, replay, automation writes) are commented
  out or opt-in so a first run is safe. Enable them deliberately.
