#!/usr/bin/env bash
# Builds the plugin zip with the Decky CLI installed by .vscode/setup.sh.
# The CLI needs root (it drives a build container and sets file ownership), so
# it runs under plain sudo -- interactively, with a clean environment, and with
# no password on any command line.
set -euo pipefail

PLUGIN_DIR="$(pwd)"
CLI_LOCATION="${PLUGIN_DIR}/cli"

if [[ ! -x "${CLI_LOCATION}/decky" ]]; then
    printf 'Decky CLI not found at %s/decky -- run the "depsetup" task first.\n' "$CLI_LOCATION" >&2
    exit 1
fi

printf 'Building plugin in %s\n' "$PLUGIN_DIR"
printf 'sudo will prompt for your password if it is not already cached.\n'

sudo "${CLI_LOCATION}/decky" plugin build "$PLUGIN_DIR"
