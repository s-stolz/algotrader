# Install AlgoTrader

Install [Docker with Compose](https://docs.docker.com/get-started/get-docker/),
start Docker, and extract the complete release ZIP. Docker Compose 2.30 or newer
and Linux containers are required. No Git, Python, Node, or Make installation is
needed. Downloads require internet access; public images need no GitHub login.

On macOS or Linux:

```sh
bash ./algotrader.sh setup
```

On Windows, open PowerShell in the extracted folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\algotrader.ps1 setup
```

Windows support is experimental until an end-to-end Docker Desktop installation
has been validated. macOS and Linux images support ARM64 and AMD64.

Setup checks Docker, suggests standard per-user directories, downloads the exact
release images, and guides broker authorization. It opens no application ports
outside the local computer. The application normally opens at
`http://localhost:8088`; setup asks for another port if that one is unavailable.

## Broker connection

Register your own application in the
[cTrader Open API portal](https://help.ctrader.com/open-api/api-application/).
Spotware must approve the application. Register exactly
`http://localhost:8080/redirect` as a redirect URI; the Playground redirect does
not work for this installation.

Enter that application's client ID and secret. Choose demo or live, then choose
view-only market data/backtesting or permission to submit broker orders. Open the
local link shown by setup, approve access in cTrader, and select your account.
The callback must return the matching authorization state; an absent or mismatched
state stops authorization without replacing credentials. Setup saves tokens locally
and the broker refreshes them. No AlgoTrader-operated login service is
involved. If approval or authorization is not ready, rerun setup later.

After setup, add a market in the application. A broker market starts collecting
new candles and offers an optional historical download. Custom markets accept
CSV uploads and do not subscribe to the broker. History requests run in the
background and resume after a service restart; explicit cancellation preserves
candles already stored.

## Files and commands

Defaults are:

| Platform | Directories |
| --- | --- |
| macOS | `~/Library/Application Support/AlgoTrader/{config,data,state}` |
| Windows | `%LOCALAPPDATA%\AlgoTrader\{config,data,state}` |
| Linux | `$XDG_CONFIG_HOME/algotrader`, `$XDG_DATA_HOME/algotrader`, `$XDG_STATE_HOME/algotrader`, with standard XDG fallbacks |

To choose another root, use `--directory /path/to/AlgoTrader` on macOS/Linux or
`-Directory C:\path\AlgoTrader` on Windows. Use the same override for subsequent
commands, including commands from a newly downloaded release ZIP. Each directory
has an independent Compose project and named database/Redis volumes. Keep the
configuration and state directories private: they contain credentials and backups.

Replace `setup` with `start`, `stop`, `status`, or `reconnect`. For example:

```sh
bash ./algotrader.sh status
bash ./algotrader.sh stop
bash ./algotrader.sh start
bash ./algotrader.sh reconnect
```

`stop` preserves volumes. Services resume when Docker restarts unless explicitly
stopped. `reconnect` can change access permissions or application credentials, but
must authorize the same account and environment. Create a separate installation
to use another account. If reconnect fails, the broker stays stopped; rerun
`reconnect` to finish before using `start`. The private `broker.env` intermediate
file is retained if token replacement could not be confirmed.

The launcher runs a temporary installer container with access to the local Docker
socket so it can manage this installation. Application containers have no socket
access. Do not use the launcher with a remote Docker engine.

Advanced settings belong in `config/topology.local.yaml`; secrets belong in
`config/.env.secrets.local`. Generated `.env.shared` and service env files are
outputs, not editable inputs. Internal service names and ports are fixed by the
release proxy; keep their defaults. Resource/logging overrides remain supported.

## Upgrade

Download and extract the desired newer release ZIP, then run its launcher with
`upgrade` and the same installation-directory override, if any:

```sh
bash ./algotrader.sh upgrade
```

Upgrades are explicit; there is no automatic update or downgrade. Alpha releases
are selected explicitly in the same way. The installer downloads images first,
blocks new backtest submissions, and refuses an upgrade while runs are queued,
running, cancelling, or an execution slot is held/faulted. Finish or cancel those
runs before retrying.

After all application writers stop, it creates a validated PostgreSQL dump, a
stopped-Redis archive, and a configuration/old-release archive under
`state/backups/`. If backup fails, no migrations run. The installer then starts
the new database image, applies ledgered migrations, starts services, verifies the
broker account, and records the new version. Interrupted history requests resume.

A failed migration leaves application services stopped and records a recovery
marker. Do not remove the marker just to restart. Keep the backup and failed
volumes; follow its `RECOVERY.md`. Automatic rollback and PostgreSQL-major-version
upgrades are not supported.

## Manual recovery into fresh storage

Every backup contains `database.dump`, `redis.tar.gz`, `configuration.tar.gz`,
`backup.json` checksums, and `RECOVERY.md`. Restore into a **separate** directory
and project, preserving the original volumes. Use the archived image digests.

1. Verify checksums from `backup.json` and extract the configuration archive. Its
   `release/release.json` identifies the previous TimescaleDB, Redis, application,
   and installer images. Its `config/.env.secrets.db` supplies PostgreSQL credentials.
2. Create fresh named volumes, for example `algotrader-recovery-db` and
   `algotrader-recovery-redis`. Start the archived database image on the first volume
   with **both** archived env files, without publishing a port. `.env.shared`
   supplies the database name/user; `.env.secrets.db` supplies its password.
   Set `TIMESCALE_IMAGE` to the archived TimescaleDB image digest, then run:

   ```sh
   docker volume create algotrader-recovery-db
   docker run --detach --name recovery-db --env-file /path/to/recovered/config/.env.shared --env-file /path/to/recovered/config/.env.secrets.db --mount type=volume,source=algotrader-recovery-db,target=/var/lib/postgresql "$TIMESCALE_IMAGE"
   docker exec recovery-db pg_isready -h 127.0.0.1 -U postgres
   ```

   Wait until the TCP readiness command succeeds; use the archived user if customized.
3. In that disposable database container, replace its empty bootstrap database
   before importing. Run these commands separately, using the archived database
   name/user when customized:

   ```sh
   docker exec recovery-db dropdb -U postgres finance_data
   docker exec recovery-db createdb -U postgres finance_data
   docker exec recovery-db psql -U postgres -d finance_data -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;'
   docker exec recovery-db psql -U postgres -d finance_data -v ON_ERROR_STOP=1 -c 'SELECT timescaledb_pre_restore();'
   ```

   Copy the dump into the container with `docker cp`, then restore and finish:

   ```sh
   docker cp /path/to/backup/database.dump recovery-db:/tmp/database.dump
   docker exec recovery-db pg_restore --exit-on-error --no-owner -U postgres -d finance_data /tmp/database.dump
   docker exec recovery-db psql -U postgres -d finance_data -v ON_ERROR_STOP=1 -c 'SELECT timescaledb_post_restore();'
   ```

   These commands preserve the migration ledger from the dump. Do not apply the
   newer release's migrations during restoration.
4. With Redis stopped, use the archived installer image's `tar` command to extract
   `redis.tar.gz` into the fresh Redis volume, preserving ownership. Start the
   archived Redis image with append-only persistence. This restores current broker
   tokens as well as streams; Redis is not disposable cache.
5. Point the archived Compose file at the fresh volumes using a Compose override
   with external named volumes. Adjust its env-file paths to the extracted config
   directory, populate `IMAGE_*` variables from the archived release manifest,
   and choose a different loopback UI port. Run `docker compose config --quiet`
   before starting the archived application images. Verify broker account, markets,
   candles, and saved backtests before retiring the failed installation.

For TimescaleDB restore rationale, see the
[official backup and restore guide](https://docs.timescale.com/self-hosted/latest/backup-and-restore/logical-backup/).

## Publishing releases (maintainers)

Push `vMAJOR.MINOR.PATCH` or a prerelease such as `v0.2.0-alpha.1` for a commit
contained in `main`. The workflow refuses tags outside main and refuses to
replace an existing GitHub Release. It tests source, builds ARM64/AMD64 images,
checks anonymous access, runs disposable image/storage smoke tests on both
architectures, then publishes the ZIP and its checksum.

**One-time GHCR setup:** newly created packages are private even when their
repository is public. After the first build, open each AlgoTrader package's
**Package settings → Change visibility → Public**, then rerun the failed workflow.
The anonymous-access gate deliberately prevents publishing an unusable ZIP before
this is done. Subsequent tags require no user login to install. See
[GitHub's package visibility instructions](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

Real cTrader authorization still needs a manual demo-account acceptance run.
Automated release smoke does not use or publish broker credentials.
