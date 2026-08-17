# Troubleshooting

### Diagnostic Bundle

The **Create Diagnostic Bundle** button in the plugin's Troubleshooting section writes a zip to `$DECKY_PLUGIN_SETTINGS_DIR/ed-jm-diagnostics.zip`. Attach it when raising an issue.

| File | Contents |
|------|----------|
| `runtime_state.json` | Python version, plugin version, watcher state, file positions, known files, settings summary, submitter stats |
| `settings.json` | Raw settings dump |
| `plugin.json` | Plugin metadata |
| `plugin.log` | Decky plugin log (if available) |

### SSL/Certificate Errors

Decky Loader embeds Python 3.11 via PyInstaller, which may not find system CA certificates. If you see upload failures with SSL errors:

1. Set the `SSL_CERT_FILE` environment variable pointing to a CA bundle before launching Decky:
   ```bash
   export SSL_CERT_FILE=/etc/ssl/cert.pem
   ```
2. The plugin automatically tries: `SSL_CERT_FILE` env → certifi bundle → system CA paths (`/etc/ssl/cert.pem`, `/etc/ssl/certs/ca-certificates.crt`, `/etc/pki/tls/certs/ca-bundle.crt`) → fallback
3. If all paths fail, the default SSL context is used (will likely fail on Decky). Enable **Detailed Logging** to see which SSL source was selected.

### Journal Path Not Found

- Auto-detection only works for Steam installs (scans `libraryfolders.vdf`)
- Non-Steam installs (Lutris, Heroic, flatpak, custom Wine prefixes) require manual path entry
- If the watcher never starts when ED launches, check that the journal path is set in the Configuration section
- Click **Re-scan for Journal Path** to retry auto-detection after installing ED

### EDDN Submission Failures

- **HTTP 429 (Rate Limited)**: Transient — the plugin retries up to 3 times with exponential backoff. Repeated 429s in Recent Errors means EDDN is throttling; events will eventually succeed.
- **HTTP 4xx (Client Error)**: Permanent — the event failed validation. Check Recent Errors for the specific error message from EDDN.
- **HTTP 5xx (Server Error)**: Transient — EDDN is having issues. The plugin retries automatically.
- **Network Error**: Check your internet connection. The plugin retries automatically.

### Plugin Not Detecting ED Start

- Game lifecycle detection requires `SteamClient.GameSessions` which may be unavailable on some SteamOS versions — the plugin logs a warning but doesn't show this in the UI
- If ED was already running when the plugin loaded, it uses `/proc` scanning and journal file modification time heuristics to detect this
- As a workaround, you can manually toggle the **Enabled** switch off/on to trigger watcher startup

### Watcher Not Starting After System Resume

The plugin registers for suspend/resume notifications and checks consistency on resume. If the watcher is stale after resuming your Deck while ED is running, try toggling **Enabled** off and back on.
