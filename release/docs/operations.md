# Manage an installation

For first-time setup, follow the [installation guide](../README.md).

## Directories and commands

The setup wizard suggests these directories:

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

Use the launcher from your **installed version's** release ZIP for these commands.
An older or newer controller is rejected before changing runtime configuration.
Use a newer ZIP only for the explicit `upgrade` command.

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
outputs, not editable inputs. The installer manages internal service names and
ports to match the release proxy; saved internal-port overrides do not change
those generated values. Resource/logging overrides remain supported.

## Development and release installations

A source checkout and a packaged installation use separate Compose projects,
networks, and database/Redis volumes. Their data is independent. Running both
uses additional Docker resources and creates separate broker connections.

New release installations suggest `http://localhost:8000`; setup asks for another
port if it is occupied. Existing installations keep their saved application port,
including `8088` from v0.0.1. Development uses `5173` for its frontend and separate
API ports. Only the release frontend is published to the host; its database and
backend services remain internal.

Authorization temporarily uses host port `8080`. If setup reports that it is
occupied, stop the process using it and retry. Older development configurations
may publish the realtime health endpoint on that port. Keep the registered
cTrader redirect `http://localhost:8080/redirect` unchanged.

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
upgrades are not supported. See [manual recovery](recovery.md) for restoring
into fresh storage.
