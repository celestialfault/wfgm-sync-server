# wfgm-sync-server

A minimal web server built with FastAPI, providing cloud sync capabilities for [Wildfire's Female Gender Mod].

**NOTE:** This currently requires [using my fork with cloud sync support](https://github.com/celestialfault/WildfireFemaleGenderMod/tree/feature/cloud-sync).

## Running your own

This requires the following to run:

- A MongoDB server with replication support enabled
- Python 3.10 or newer
- [Poetry](https://python-poetry.org/)

```sh
git clone https://github.com/celestialfault/wfgm-sync-server.git
cd wfgm-sync-server
poetry install
poetry run fastapi run
```

[Wildfire's Female Gender Mod]: https://github.com/WildfireRomeo/WildfireFemaleGenderMod
