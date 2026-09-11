#!/usr/bin/env bash
# Installs the local toolchain needed to build the plugin: pnpm (via corepack or
# your distro's package manager -- never a piped remote install script) and the
# Decky CLI, pinned to an exact release tag and verified by SHA-256 before it is
# made executable.
set -euo pipefail

# --- Decky CLI pin -----------------------------------------------------------
# Pinned to the tagged release below. releases/latest/download/ is deliberately
# NOT used: that URL is mutable, so no digest could be pinned against it.
#
# To move to a newer CLI release, bump DECKY_CLI_VERSION and recompute every
# digest, e.g.:
#   for a in decky-linux-x86_64 decky-linux-aarch64 decky-macOS-x86_64 decky-macOS-aarch64; do
#     curl -fsSL "https://github.com/SteamDeckHomebrew/cli/releases/download/<tag>/$a" | sha256sum
#   done
DECKY_CLI_VERSION="0.0.8"
DECKY_CLI_BASE_URL="https://github.com/SteamDeckHomebrew/cli/releases/download/${DECKY_CLI_VERSION}"
# SHA-256 digests of the Decky CLI 0.0.8 release artifacts.
DECKY_CLI_SHA256_LINUX_X86_64="6777e356508c1ce887f8e61b0fa4954bb48b32e6d97341eef68ea4e0d6ead9a0"
DECKY_CLI_SHA256_LINUX_AARCH64="ea4cad1f4ae2dd12ff30c89fb416268f0524498d6014e5d94db9288b2ede7737"
DECKY_CLI_SHA256_MACOS_X86_64="77c0b56ad054753987ed96a500154718d8efef10ed0bc42f876d3af99ded2d00"
DECKY_CLI_SHA256_MACOS_AARCH64="dc995da824da17c2baa32f0076d5d2609f3300e04b87949966a898dd0910aa59"
# -----------------------------------------------------------------------------

REPO_ROOT="$(pwd)"
CLI_DIR="${REPO_ROOT}/cli"
CLI_BINARY="${CLI_DIR}/decky"

echo "If you are using alpine linux, do not expect any support."

have() {
    command -v "$1" > /dev/null 2>&1
}

sha256_of() {
    local file="$1"
    if have sha256sum; then
        sha256sum "$file" | cut -d ' ' -f 1
    elif have shasum; then
        shasum -a 256 "$file" | cut -d ' ' -f 1
    elif have openssl; then
        openssl dgst -sha256 "$file" | awk '{print $NF}'
    else
        printf 'no sha256sum, shasum or openssl available -- cannot verify downloads.\n' >&2
        return 1
    fi
}

fetch() {
    local url="$1" dest="$2"
    if have curl; then
        curl -fsSL --proto '=https' --tlsv1.2 -o "$dest" "$url"
    elif have wget; then
        wget -q --https-only -O "$dest" "$url"
    else
        printf 'neither curl nor wget is installed -- cannot download %s\n' "$url" >&2
        return 1
    fi
}

install_pnpm() {
    # corepack ships with Node.js and activates pnpm from the Node distribution
    # itself, so there is no remote script to pipe into a shell.
    if have corepack; then
        printf 'Enabling pnpm via corepack.\n'
        if corepack enable pnpm && corepack prepare pnpm@latest --activate; then
            return 0
        fi
        printf 'corepack could not activate pnpm (it may need write access to your Node install; try it under sudo).\n' >&2
        return 1
    fi
    printf 'corepack was not found. Install pnpm using one of:\n' >&2
    printf '  * your distro package manager (pacman -S pnpm / apt install pnpm / dnf install pnpm)\n' >&2
    printf '  * Node.js >= 16.9, which ships corepack: then run "corepack enable pnpm"\n' >&2
    printf '  * npm install -g pnpm\n' >&2
    return 1
}

decky_cli_artifact() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"
    case "${os}:${arch}" in
        Linux:x86_64)             printf 'decky-linux-x86_64 %s' "$DECKY_CLI_SHA256_LINUX_X86_64" ;;
        Linux:aarch64|Linux:arm64) printf 'decky-linux-aarch64 %s' "$DECKY_CLI_SHA256_LINUX_AARCH64" ;;
        Darwin:x86_64)            printf 'decky-macOS-x86_64 %s' "$DECKY_CLI_SHA256_MACOS_X86_64" ;;
        Darwin:aarch64|Darwin:arm64) printf 'decky-macOS-aarch64 %s' "$DECKY_CLI_SHA256_MACOS_AARCH64" ;;
        *)
            printf 'unsupported platform "%s %s" -- only Linux and macOS on x86_64/arm64 are supported.\n' "$os" "$arch" >&2
            return 1
            ;;
    esac
}

install_decky_cli() {
    local artifact expected spec url tmp actual
    # An unsupported platform must abort here, never fall through to chmod +x.
    if ! spec="$(decky_cli_artifact)"; then
        return 1
    fi
    read -r artifact expected <<< "$spec"

    url="${DECKY_CLI_BASE_URL}/${artifact}"
    mkdir -p "$CLI_DIR"
    tmp="$(mktemp "${CLI_DIR}/.decky.XXXXXX")"

    printf 'Downloading Decky CLI %s (%s)\n' "$DECKY_CLI_VERSION" "$artifact"
    if ! fetch "$url" "$tmp"; then
        rm -f "$tmp"
        return 1
    fi

    if ! actual="$(sha256_of "$tmp")"; then
        rm -f "$tmp"
        return 1
    fi

    if [[ "$actual" != "$expected" ]]; then
        rm -f "$tmp"
        printf 'SHA-256 mismatch for %s\n  expected: %s\n  actual:   %s\nRefusing to install the download.\n' \
            "$artifact" "$expected" "$actual" >&2
        return 1
    fi

    # Only now, after the digest matched, does the download become executable.
    printf 'SHA-256 verified: %s\n' "$actual"
    chmod 0755 "$tmp"
    mv -f "$tmp" "$CLI_BINARY"
    printf 'Decky CLI installed at %s. Build with the "cli-build" task.\n' "$CLI_BINARY"
}

if ! have pnpm; then
    printf 'pnpm is not installed.\n'
    printf 'Hit enter to install it with corepack, or type "no" to install it yourself.\n'
    run_pnpm_setup=""
    read -r run_pnpm_setup || true
    case "$run_pnpm_setup" in
        [nN]*)
            printf 'Skipping pnpm setup. Install pnpm before building the plugin.\n'
            ;;
        *)
            if ! install_pnpm; then
                printf 'pnpm setup did not complete -- see the guidance above.\n' >&2
                exit 1
            fi
            ;;
    esac
fi

if ! have docker; then
    echo "Docker is not currently installed, in order build plugins with a backend you will need to have Docker installed. Please install Docker via the preferred method for your distribution."
fi

if [[ ! -f "$CLI_BINARY" ]]; then
    printf 'The Decky CLI tool (the "decky" binary) builds your plugin into an installable zip.\n'
    printf 'Hit enter to download Decky CLI %s into ./cli (pinned by release tag and verified by SHA-256), or type "no" to skip.\n' \
        "$DECKY_CLI_VERSION"
    run_cli_setup=""
    read -r run_cli_setup || true
    case "$run_cli_setup" in
        [nN]*)
            printf 'Skipping Decky CLI setup. You will not be able to build a plugin zip without it.\n'
            ;;
        *)
            install_decky_cli
            ;;
    esac
fi
