# Recover an installation

Use this guide after an upgrade failure, alongside the backup’s metadata and
recovery marker. It restores the archived version into fresh storage.

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
