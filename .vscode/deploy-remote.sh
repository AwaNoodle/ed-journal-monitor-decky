#!/usr/bin/env bash
# Runs ON the Steam Deck. Invoked from .vscode/deploy.sh as:
#
#   bash <this script> <deck-home-dir> <plugin-name>
#
# Both values arrive as positional arguments; nothing is ever concatenated into
# a shell command string here. sudo prompts on the terminal allocated by
# `ssh -t`, so no password is passed on a command line or through a pipe.
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'usage: deploy-remote.sh <deck-home-dir> <plugin-name>\n' >&2
    exit 2
fi

deck_dir="$1"
plugin_name="$2"

# Defence in depth: the caller validates too, but this script is the thing that
# feeds values to sudo, so it re-checks rather than trusting its invoker.
if [[ ! $plugin_name =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf 'refusing to deploy: plugin name "%s" must match [A-Za-z0-9._-]+ (no spaces, quotes or shell metacharacters)\n' "$plugin_name" >&2
    exit 1
fi

if [[ ! $deck_dir =~ ^/[A-Za-z0-9._/-]*$ ]]; then
    printf 'refusing to deploy: deck directory "%s" must be an absolute path matching /[A-Za-z0-9._/-]*\n' "$deck_dir" >&2
    exit 1
fi

plugins_dir="${deck_dir}/homebrew/plugins"
target_dir="${plugins_dir}/${plugin_name}"
zip_file="${plugins_dir}/${plugin_name}.zip"

if [[ ! -f $zip_file ]]; then
    printf 'no plugin archive at %s -- run the copyzip task first (and check that "pluginname" matches the built zip name)\n' "$zip_file" >&2
    exit 1
fi

printf 'Extracting %s into %s\n' "$zip_file" "$target_dir"
printf 'sudo will prompt for your Steam Deck password if it is not already cached.\n'

sudo mkdir -m 755 -p "$target_dir"
sudo chown "$(id -un):$(id -gn)" "$target_dir"
sudo bsdtar -xzpf "$zip_file" -C "$target_dir" --strip-components=1 --fflags

printf 'Deployed %s\n' "$plugin_name"
