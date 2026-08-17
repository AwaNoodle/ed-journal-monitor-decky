<img src="assets/logo.png" alt="ED Journal Monitor" width="96" align="left">

# ED Journal Monitor

**Contribute to EDDN from your Steam Deck, without ever leaving Game Mode.**

[![Build](https://github.com/AwaNoodle/ed-journal-monitor-decky/actions/workflows/build.yml/badge.svg)](https://github.com/AwaNoodle/ed-journal-monitor-decky/actions/workflows/build.yml)
[![GitHub Release](https://img.shields.io/github/v/release/AwaNoodle/ed-journal-monitor-decky)](https://github.com/AwaNoodle/ed-journal-monitor-decky/releases)
[![License: MIT](https://img.shields.io/github/license/AwaNoodle/ed-journal-monitor-decky)](LICENSE)

A [Decky](https://github.com/SteamDeckHomebrew/decky-loader) plugin that watches your Elite Dangerous journal files and submits events to the [Elite Dangerous Data Network (EDDN)](https://eddn.edcd.io/) - and, optionally, to your [EDSM](https://www.edsm.net/) commander profile.

## Why

[EDMC](https://github.com/EDCD/EDMarketConnector) is the established way to feed EDDN, and it can be run on a Steam Deck. This plugin is an alternative for people already running Decky who would rather stay in Game Mode.

It lives in the quick access menu alongside your other plugins, starts and stops with the game, needs no root access, and finds your journal directory by itself on Steam installs. Set it up once and forget it exists.

It also uses that same journal stream to tell you things while you fly - whether the system you just arrived in is worth scanning, what your next hop looks like before you jump, and where the nearest fuel-scoopable star is.

## Screenshots

<!--
  TODO: capture and add.
  1. assets/screenshot-panel.png - quick access panel open in Game Mode, showing the
     health strip, Navigation (with a worth-scanning chip + next hop), and Session counters.
  2. assets/screenshot-toast.png - a worth-scanning toast over the running game.
  Then replace this comment with the image tags.
-->

_Not captured yet._

## Features

- **Built for the Deck** - no root access, lightweight polling watcher, and a panel ordered so in-flight information is visible without scrolling past setup controls
- **Hands-off EDDN submission** - detects when Elite Dangerous starts and stops, and submits journal, market, outfitting, shipyard, and exploration events without you touching anything
- **Live session dashboard** - jumps, distance travelled, bodies scanned, and first discoveries for the current game launch
- **Automatic setup** - finds your journal directory by scanning Steam's library configuration, and fills in your EDDN uploader ID from your CMDR name
- **In-flight navigation aids** (optional) - on arrival, an EDSM-sourced verdict on whether the system is worth scanning and its estimated scan value; a preview of your next hop and whether its star is scoopable; and an on-demand search for the nearest scoopable star
- **Arrival notifications** (optional) - a Steam toast when you jump into a system worth scanning, visible over the running game, so you can decide whether to honk without opening a menu
- **EDSM forwarding** (optional) - mirror your journal to your own EDSM commander profile, fully isolated from EDDN so a failure on one never affects the other
- **Diagnostics** - a detailed logging toggle and a one-button diagnostic bundle for when something needs investigating

## Requirements

- A Steam Deck (or other SteamOS / Linux handheld) running [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
- Elite Dangerous installed - via Steam for automatic journal discovery, or any other launcher with a [manually configured path](#journal-path)

## Installation

The plugin is not yet listed in the Decky Plugin Store, so install it from a release zip.

1. Download `ed-journal-monitor.zip` from the [latest release](https://github.com/AwaNoodle/ed-journal-monitor-decky/releases/latest), or build it yourself (see [Contributing](#contributing)).
2. Copy it to your Deck, either by switching to Desktop Mode and copying to `~/Documents/`, or over the network:
   ```bash
   scp ed-journal-monitor.zip deck@<steamdeck-ip>:~/Documents/
   ```
3. In Decky's settings, enable **Developer Mode**.
4. Use **Install Plugin from ZIP** and select the file.

## Quick start

Once installed, there is nothing to configure for a standard Steam install:

1. Launch Elite Dangerous.
2. Open the Decky quick access menu and select **ED Journal Monitor**.
3. The health strip at the top should read **Watching**.

That's it - events are being submitted. The panel is ordered by how often you look at each part: the health strip, **Navigation**, and **Session** are always visible, while **Data flow**, **Setup**, and **Troubleshooting** stay collapsed until you need them.

### Confirming your data is arriving

- **[EDDN Status Page](https://eddn.edcd.io/)** - a live feed of all EDDN submissions.
- **[eddn-tail](https://github.com/AwaNoodle/eddn-tail)** - a CLI tool that tails the live feed. Filter by the system you're currently in and watch your own jumps and scans appear:
  ```bash
  eddn-tail --system "Sol"
  ```
  EDDN's relay obfuscates `uploaderID` to prevent long-term tracking of players, so you can't find your submissions by CMDR name - filtering by system is the practical way to spot them.
- **Your EDSM profile** - if EDSM forwarding is enabled, recent jumps and scans should appear on [edsm.net](https://www.edsm.net/).

## Configuration

Everything below lives under **Setup** in the plugin panel, except detailed logging.

### Journal path

The plugin scans for your journal directory on first launch, and re-scans when you start the game if it wasn't found. You only need to do something here if auto-detection fails - which it will for non-Steam installs such as Lutris, Heroic, flatpak, or a custom Wine prefix.

Under **Setup ▸ Journal path**, either press **Re-scan for Journal Path**, or enter the directory manually. A typical Proton path looks like:

```
~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
```

> The scan looks under `drive_c/users/*/Saved Games/...` - your username may not be `steamuser` depending on your Proton configuration.

The same group holds the **Watch journal** toggle. Turning it off stops the watcher starting even while ED is running; the health strip then reports watching as paused.

### Uploader ID

Set automatically from your CMDR name when a game session loads, and editable under **Setup ▸ EDDN**. EDDN asks senders for a meaningful identifier and recommends your CMDR name; its relay then obfuscates the value before messages reach listeners, so this is not published as-is.

### Optional: EDSM lookups

Under **Setup ▸ EDSM lookups**, the **Enable EDSM lookup** toggle (off by default) turns on all three navigation aids. They read EDSM's public API and need no account or API key.

- **Worth scanning** - on arrival, a green (unexplored), yellow (partially explored), or red (fully explored) chip based on EDSM's body data.
- **System value** - EDSM's estimated scan value and the highest-value bodies. This is a floor: it covers only bodies EDSM knows about and excludes any first-mapped bonus.
- **Next hop** - when a route is plotted, the next system's name, whether its primary star is scoopable, and its verdict and value. Scoopability comes from the route itself, so it works even when EDSM has no data. Always shown, and says plainly when there's no route, you've arrived, or you're off route.
- **Find Nearest Scoopable Star** - an on-demand search of a 25 ly sphere for the closest system with a scoopable primary star. On demand rather than per-jump to keep traffic on EDSM's API low. If lookups are off, pressing the button turns them on and runs the search in one go.

### Optional: worth-scanning notifications

With lookups enabled, the **'Worth-scanning' Notifications** toggle raises a Steam toast on arrival in a system worth scanning - visible over the running game. A second toggle sets the threshold: green only (default), or green and yellow. Red and neutral verdicts never notify. Tapping the toast opens the plugin panel.

Two limitations worth knowing:

- **Steam can suppress the toast.** Steam's "notifications while in game" preference and Do Not Disturb both swallow it, outside this plugin's control. If you see nothing, check those first.
- **No dedupe.** Suppression is per-arrival, so revisiting a system (A → B → A) notifies you again.

### Optional: EDSM forwarding

The plugin can forward your journal to your [EDSM](https://www.edsm.net/) commander profile alongside EDDN.

> **This is identifiable.** Unlike EDDN's hashed uploader IDs, EDSM uploads are tied to your named account and appear on your commander profile - flight logs, visited systems, scans. It is off by default, and saving an API key is how you consent to it.

Under **Setup ▸ EDSM account**, enter your commander name as registered on EDSM, and an API key from [Settings → My API Key](https://www.edsm.net/en/settings/api). Forwarding activates on the next game session.

It is fully isolated from EDDN - bad EDSM credentials surface as a "check your EDSM credentials" message and never affect EDDN submission, or vice versa. Only the Live game version is forwarded. Note that this key is only needed for forwarding; the EDSM lookups above work without one.

### Optional: detailed logging

The **Detailed Logging** toggle in the panel's **Troubleshooting** section switches log verbosity from INFO to DEBUG for richer diagnostic output. Persists across restarts.

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for SSL errors, journal path problems, submission failures, and detection issues.

If you need to raise an issue, the **Create Diagnostic Bundle** button under **Troubleshooting** packages logs, settings, and runtime state into a zip - attach it to your report.

## Documentation

| Document | Contents |
|----------|----------|
| [developer-guide.md](developer-guide.md) | Architecture, event flow, EDDN event coverage, known limitations |
| [troubleshooting.md](troubleshooting.md) | Common problems and fixes |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [AGENTS.md](AGENTS.md) | Detailed conventions and module-level design notes |

Events are submitted to `https://eddn.edcd.io:4430/upload/` under `softwareName: ED Journal Monitor Decky`, covering the `journal/1`, `commodity/3`, `outfitting/2`, `shipyard/2`, `navroute/1`, and several dedicated exploration and docking schemas. The full event-to-schema mapping is in the [developer guide](developer-guide.md#eddn-event-coverage).

## Contributing

Contributions are welcome. Please read [AGENTS.md](AGENTS.md) first - it carries the conventions this repo actually enforces.

### Setup

```bash
npm install                 # frontend dependencies
npm run build               # bundle frontend to dist/
npm run package             # build + zip into ed-journal-monitor.zip
```

Python 3.9+ is required for the backend, which uses the standard library only - no pip packages at runtime.

### Before you open a PR

```bash
npm run test                # pytest (or: PYTHONPATH=. .venv/bin/python -m pytest tests/ -v)
npm run lint:ts
npm run lint:py
```

All tests must pass. Tests are expected alongside the change, not after it.

### Workflow

- Work on a dedicated branch or worktree - never commit directly to `main`.
- Integrate via pull request, merged with **squash and rebase** to keep history linear.
- Add an entry under `[Unreleased]` in `CHANGELOG.md`. Keep it to one or two user-facing sentences; these become the release notes.
- Changes touching event transformation, validation, filtering, or submission must follow the [EDDN Developers Guide](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md) and the relevant [schema README](https://github.com/EDCD/EDDN/tree/live/schemas).

## License

[MIT](LICENSE)
