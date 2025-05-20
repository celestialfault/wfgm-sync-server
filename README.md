# This project has moved

**This repository now lives on [Codeberg].**

GitHub is a software forge that is now actively anti-open source maintainers, by introducing new artificial "intelligence"
features, the primary purpose of which is to waste maintainer time by creating issues and pull requests that nobody
bothered to write, using plagiarised code which does not respect the original source's license.[^1]

This is deeply unacceptable, and I am no longer willing to host my projects on a software forge that is
as actively anti-maintainer as GitHub is.

------

# wfgm-sync-server

A minimal web server built with FastAPI, providing cloud sync capabilities for [Wildfire's Female Gender Mod].

## Running your own

This requires the following to run:

- A MongoDB server with replication support enabled
  - [MongoDB Atlas](https://www.mongodb.com/atlas) provides free databases with to 512 MB of storage, suitable for local development
- Python 3.10 or newer
- [Poetry](https://python-poetry.org/)

```sh
git clone https://github.com/celestialfault/wfgm-sync-server.git
cd wfgm-sync-server
poetry install --only main
poetry run fastapi run
```

Afterward, point the mod at your server by setting `cloud_server` in `config/wildfire_gender.json` to your server,
such as `https://wfgm.example.com`.

Note that there is a known issue where the mod will fail to sync player data to the server if it isn't running over
HTTPS - this issue is automatically worked around if you're in a development environment (to allow for local development),
but this otherwise effectively forces an HTTPS requirement for production deployments (which you should already be doing
to begin with).

[^1]: https://github.com/orgs/community/discussions/159749

[Codeberg]: https://codeberg.org/celestialfault/wfgm-sync-server
[Wildfire's Female Gender Mod]: https://github.com/WildfireRomeo/WildfireFemaleGenderMod
