# Install AlgoTrader

## 1. Prepare Docker and your cTrader application

**Broker account.** Use your existing cTrader demo or live account. If you need
an account, IC Trading is one option. The AlgoTrader maintainer may earn a
commission if you sign up through this [IC Trading affiliate link](https://www.ictrading.com?camp=86158).

Install [Docker with Compose](https://docs.docker.com/get-started/get-docker/)
and start it. Use Compose 2.30 or newer and Linux containers. You do not need
Git, Python, Node, or Make.

Register your own application in the
[cTrader Open API portal](https://openapi.ctrader.com/apps) and wait for Spotware
approval. See [cTrader’s application guide](https://help.ctrader.com/open-api/api-application/)
for the registration steps. In that application's **Redirect URIs**, add exactly:

```text
http://localhost:8080/redirect
```

Keep its **client ID and client secret** ready. The default Playground redirect
will not work. You do not need an account ID or access token in advance.

## 2. Download the installer

From [GitHub Releases](https://github.com/s-stolz/algotrader/releases/latest),
download **`algotrader-VERSION.zip`** and extract the whole ZIP.
The same installer supports macOS, Linux, and Windows; Docker selects the image
for your computer. Downloads require internet access but no GitHub login.

The `.zip.sha256` file is for checking download integrity. GitHub’s **Source code**
archives contain the development source, not the installer.
Windows support is experimental until an end-to-end Docker Desktop installation
has been validated.

## 3. Run setup

Open a terminal in the extracted folder. On macOS or Linux, run:

```sh
bash ./algotrader.sh setup
```

On Windows, open PowerShell in that folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\algotrader.ps1 setup
```

Follow the prompts to choose an installation directory, enter your application
credentials, and choose demo or live access. Choose view-only access for market
data and backtesting, or trading access if you need to submit broker orders.

Open the wizard’s authorization link on this computer and approve access in
cTrader. Keep the terminal open: your browser returns to a temporary local server,
then setup asks you to confirm the discovered account. Press Enter to accept a
single account, or select a number when several accounts are listed.

If cTrader reports **“Provided application does not contain provided URI”**, check
that the exact redirect above is saved on the application matching your client ID.
If setup exits, run the same setup command again.

## 4. Open AlgoTrader

Open the address printed by setup, normally **http://localhost:8000** for a new
installation. Setup lets you choose another port if needed.

Add a broker market to collect live candles and optionally download older data.
Choose a Custom market to upload CSV data instead.

## After setup

From the same extracted folder, replace `setup` with `stop`, `start`, or `status`.
For example, on macOS/Linux:

```sh
bash ./algotrader.sh stop
bash ./algotrader.sh start
```

Stopping preserves your data. Keep the extracted folder for future commands. If
you chose a custom installation directory, supply it for later commands too.

To check for the latest stable version, run `bash ./algotrader.sh upgrade`
on macOS or Linux, or
`powershell -ExecutionPolicy Bypass -File .\algotrader.ps1 upgrade` on Windows.
The launcher shows the installed and available versions and asks before upgrading.
See the [upgrade guide](docs/operations.md#upgrade) for alpha releases and the
one-time download for v0.0.1.

For broker reconnection, directory options, and settings, see
[Manage an installation](docs/operations.md).
