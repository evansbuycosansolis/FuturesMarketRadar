# Bundled Agentic research runtime

This is the runtime subset of the locally modified **Agentic Hyperliquid Trading Desk**, based on [HyperGrok Trading Desk](https://github.com/galleonlabs/hypergrok-trading-desk) by **Andrew Wilkinson and Galleon Labs**, under the [MIT license](LICENSE). This directory does not relicense the rest of FuturesMarketRadar or imply upstream endorsement.

The source instruction version is 1.7.1, with unpublished local modifications for the provider-neutral name, standalone OpenAI application, and read-only Radar evidence bridge. It is not a claim that the upstream tag contains those modifications. Original copyright and permission notices are retained in `LICENSE` and beside each skill. See [attribution](ATTRIBUTION.md).

Included: the OpenAI local app and its offline journeys, seven role profiles, seventeen skills, and the three standard-library modules used for public market snapshots and stop-cost estimation. The parent project's integrated launcher uses this directory by default. No keys, environment files, databases, conversations, generated logs, or exchange writer are bundled.

This subset does not include the upstream installer, plugin distribution, release tooling, or every standalone command mentioned in skill prose. The app's tool allowlist remains the runtime capability boundary. Consult the full source project for other workflows.

`SOURCE_MANIFEST.json` records each copied file's SHA-256 hash. To deliberately refresh from the local source checkout, run `python scripts/sync_agentic_runtime.py --source "C:/path/to/agentic"` from the Radar repository and review the changes. The script copies only an explicit allowlist and retains notices.
