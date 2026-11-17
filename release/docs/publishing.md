# Publish a release

This guide is for maintainers. Users should follow the
[installation guide](../README.md).

Push `vMAJOR.MINOR.PATCH` or a prerelease such as `v0.2.0-alpha.1` for a commit
contained in `main`. The workflow refuses tags outside main and refuses to
replace an existing GitHub Release. It tests source, builds ARM64/AMD64 images,
checks anonymous access, runs disposable image/storage smoke tests on native
runners for both architectures, then publishes the ZIP and its checksum.

Release notes identify `algotrader-VERSION.zip` as the installer for all supported
platforms. The `.zip.sha256` asset verifies that download. GitHub automatically
adds source archives; those are for working with the source checkout.

## Public image access

Every image must be anonymously readable. If the public-access check fails,
open the affected package’s **Package settings → Change visibility → Public**,
then rerun the failed workflow. The gate prevents publishing an unusable ZIP.
See [GitHub’s package visibility instructions](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

## Acceptance checks

Automated release smoke does not use or publish broker credentials. Test real
cTrader authorization with a demo account, including the registered redirect and
account selection. Windows needs an end-to-end Docker Desktop acceptance run;
launcher syntax checks alone do not establish Windows installation support.

To test an upgrade, install an earlier release into disposable storage with a
sample market and candles. Run `upgrade` from its launcher, confirm the offered
version, then run `status` from the same folder. Check the saved application
port, broker account, credentials, markets, candles, and backtests.
