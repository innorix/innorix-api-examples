# Innorix API Examples

Runnable code examples for the [Innorix](https://www.innorix.com) file-transfer
API, in **Python, Java, Node.js, and C#**. Each language folder contains the
same set of examples so you can learn the API in whichever language you use.

The examples cover the full workflow end to end: authentication, device
discovery, one-to-one transfers, transfer control, scheduled automations, hot
folders, history/reporting, and pre-flight validation.

## Languages

| Language | Folder | Getting started |
|----------|--------|-----------------|
| Python | [`python/`](python/) | [python/README.md](python/README.md) |
| Java | [`java/`](java/) | [java/README.md](java/README.md) |
| Node.js | [`nodejs/`](nodejs/) | [nodejs/README.md](nodejs/README.md) |
| C# | [`csharp/`](csharp/) | [csharp/README.md](csharp/README.md) |

Each folder is an independent project that follows its own ecosystem's
conventions (`pip`, `maven`, `npm`, `dotnet`). Pick a language and follow its
README.

## Examples

The same numbered examples exist in every language:

| # | Example | What it shows |
|---|---------|---------------|
| 01 | Authentication | Log in and obtain an access token |
| 02 | Devices & connectivity | List devices and check whether they are online |
| 03 | Remote file explorer | Browse and manage files/folders on a device |
| 04 | One-to-one transfer | Send files between two devices and track progress |
| 05 | Transfer control | Pause, resume, cancel, and retry failed files |
| 06 | Replay | Re-run a previous transfer |
| 07 | Scheduled automation | Create a saved/scheduled transfer |
| 08 | Hot folders | Auto-transfer files dropped into a watched folder |
| 09 | Transfer history | Review completed transfers and export CSV |
| 10 | Pre-flight validation | Validate path, size, and security policy before sending |

## API reference

The OpenAPI specification for the API lives in
[`openapi/innorix-openapi.yaml`](openapi/innorix-openapi.yaml). It is the single
source of truth shared by all language examples.

## Configuration & credentials

Every example reads its configuration (API URL, workspace ID, credentials,
device IDs) from environment variables or a local `.env` file. Copy the
`.env.example` in a language folder to `.env` and fill in your own values.

> **Never commit real credentials.** `.env` files are git-ignored. Only the
> `.env.example` templates are tracked.

## Repository layout

```
innorix-api-examples/
├── README.md               # you are here
├── .gitignore
├── LICENSE
├── openapi/
│   └── innorix-openapi.yaml   # shared API specification
├── python/
├── java/
├── nodejs/
└── csharp/
```

## Contributing

When the API changes, update the OpenAPI spec and the affected examples in each
language, keeping the numbered examples aligned across languages so `04` means
the same thing everywhere.

## License

See [LICENSE](LICENSE).
