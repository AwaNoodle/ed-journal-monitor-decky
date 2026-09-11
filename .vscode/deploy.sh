#!/usr/bin/env bash
# Local driver for the VS Code deploy tasks.
#
#   deploy.sh <action>
#
# actions: copy-zip | extract | chmod-plugins | restart-decky
#
# Every settings.json value arrives through the *environment* (DECK_USER,
# DECK_IP, DECK_PORT, DECK_DIR, PLUGIN_NAME, DECK_KEY), set by the task's
# `options.env`. That matters: VS Code substitutes `${config:*}` as raw text, so
# any value spliced into a task's `command` string is parsed by the local shell
# first -- a single quote, `;` or backtick in settings.json would execute there,
# before this script could validate anything. Environment values are never
# re-parsed, so validation below is the first and only gate.
#
# Each value is then checked against a conservative charset before it reaches
# ssh/scp/rsync (which necessarily re-parse their command words with the
# *remote* shell), and the multi-command remote block lives in the checked-in
# deploy-remote.sh rather than being built up as a string.
#
# sudo on the device runs interactively over `ssh -t`: no password is stored in
# settings.json, passed on a command line, or echoed into a pipe.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" > /dev/null 2>&1 && pwd)"

if [[ $# -ne 1 ]]; then
    printf 'usage: deploy.sh <copy-zip|extract|chmod-plugins|restart-decky>\n' >&2
    printf 'configuration comes from DECK_USER/DECK_IP/DECK_PORT/DECK_DIR/PLUGIN_NAME/DECK_KEY\n' >&2
    exit 2
fi

action="$1"

die() {
    printf '%s\n' "$1" >&2
    exit 1
}

require_match() {
    local label="$1" value="$2" pattern="$3"
    if [[ ! $value =~ $pattern ]]; then
        die "refusing to run: ${label} \"${value}\" must match ${pattern} -- fix it in .vscode/settings.json"
    fi
}

user="${DECK_USER:-}"
host="${DECK_IP:-}"
port="${DECK_PORT:-}"
deck_dir="${DECK_DIR:-}"
plugin_name="${PLUGIN_NAME:-}"

require_match 'deckuser' "$user" '^[A-Za-z0-9._-]+$'
require_match 'deckip' "$host" '^[A-Za-z0-9._-]+$'
require_match 'deckport' "$port" '^[0-9]{1,5}$'
require_match 'deckdir' "$deck_dir" '^/[A-Za-z0-9._/-]*$'
require_match 'pluginname' "$plugin_name" '^[A-Za-z0-9._-]+$'

# DECK_KEY holds ssh flags (e.g. `-i ~/.ssh/id_rsa`), so it is the one value
# that must split into several arguments. Splitting happens here, on a value the
# shell has not parsed, and every resulting word is validated: ssh options that
# hand a string to a shell (ProxyCommand, LocalCommand, PermitLocalCommand) are
# rejected outright, since they would turn a hostile settings.json back into
# local code execution. A leading `~/` is expanded here because no shell will.
ssh_opts=()
if [[ -n ${DECK_KEY:-} ]]; then
    read -r -a deck_key_words <<< "$DECK_KEY"
    for word in ${deck_key_words[@]+"${deck_key_words[@]}"}; do
        shopt -s nocasematch
        if [[ $word == *proxycommand* || $word == *localcommand* ]]; then
            shopt -u nocasematch
            die "refusing to run: deckkey option \"${word}\" can execute a local command"
        fi
        shopt -u nocasematch
        require_match 'deckkey word' "$word" '^(-[A-Za-z]|[A-Za-z0-9._/~@=+:,-]+)$'
        if [[ $word == '~/'* ]]; then
            word="${HOME}/${word#\~/}"
        fi
        ssh_opts+=("$word")
    done
fi

# ssh hands its command words to a remote shell, so each word is wrapped in
# single quotes for that shell. The validation above guarantees no value can
# contain a quote, so this is unambiguous.
rq() {
    printf "'%s'" "$1"
}

run_remote() {
    ssh -t -p "$port" ${ssh_opts[@]+"${ssh_opts[@]}"} "${user}@${host}" "$@"
}

case "$action" in
    copy-zip)
        rsync -azp --chmod=D0755,F0755 \
            --rsh="ssh -p ${port} ${ssh_opts[*]-}" \
            out/ "${user}@${host}:${deck_dir}/homebrew/plugins"
        ;;
    extract)
        remote_script="${deck_dir}/.ed-journal-monitor-deploy-remote.sh"
        scp -P "$port" ${ssh_opts[@]+"${ssh_opts[@]}"} \
            "${script_dir}/deploy-remote.sh" \
            "${user}@${host}:$(rq "$remote_script")"
        run_remote bash "$(rq "$remote_script")" "$(rq "$deck_dir")" "$(rq "$plugin_name")"
        ;;
    chmod-plugins)
        run_remote sudo chown "$(rq "$user")" "$(rq "${deck_dir}/homebrew/plugins/")"
        ;;
    restart-decky)
        run_remote sudo systemctl restart plugin_loader
        ;;
    *)
        die "unknown action \"${action}\" (expected copy-zip, extract, chmod-plugins or restart-decky)"
        ;;
esac
