import { useState, useEffect, useRef } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
  Field,
  ButtonItem,
  TextField,
} from "@decky/ui";
import { addEventListener, removeEventListener } from "@decky/api";
import type { JSX } from "react";
import {
  createDiagnosticsBundle,
  findJournalPath,
  getRecentActivity,
  getSessionStats,
  getStatus,
  setDetailedLogging,
  setEdsmCredentials,
  setEdsmLookupsEnabled,
  setEnabled,
  setManualJournalPath,
  setUploaderId,
  startWatcher,
  stopWatcher,
} from "./api";

const EDSM_API_KEY_URL = "https://www.edsm.net/en/settings/api";

// Index access on the target map may miss at runtime (e.g. before the first
// status load), so read through a helper that reflects the possibly-undefined.
const readTarget = (map: TargetStatsMap, key: string): TargetStats | undefined => map[key];

const Content = (): JSX.Element => {
  const [enabled, setEnabledState] = useState(true);
  const [watcherRunning, setWatcherRunning] = useState(false);
  const [edRunning, setEdRunning] = useState(false);
  const [journalPath, setJournalPath] = useState<string | null>(null);
  const [journalPathSource, setJournalPathSource] = useState<string | null>(null);
  const [targets, setTargets] = useState<TargetStatsMap>({});
  const [uploaderId, setUploaderIdState] = useState<string>("");
  const [manualPathInput, setManualPathInput] = useState<string>("");
  const [uploaderIdInput, setUploaderIdInput] = useState<string>("");
  const [edsmCommanderInput, setEdsmCommanderInput] = useState<string>("");
  const [edsmApiKeyInput, setEdsmApiKeyInput] = useState<string>("");
  const [edsmApiKeySet, setEdsmApiKeySet] = useState<boolean>(false);
  const [edsmSaved, setEdsmSaved] = useState<boolean>(false);
  const [pathError, setPathError] = useState<string | null>(null);
  const [detailedLogging, setDetailedLoggingState] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<DiagnosticsResult | null>(null);
  const [recentErrors, setRecentErrors] = useState<ActivityEntry[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityEntry[]>([]);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [edsmLookupsEnabled, setEdsmLookupsEnabledState] = useState<boolean>(false);
  const [edsmWorthScanning, setEdsmWorthScanning] = useState<EdsmWorthScanningVerdict | null>(null);

  // Ref to track current uploaderId so the commander_detected listener
  // doesn't use a stale closure value
  const uploaderIdRef = useRef<string>("");

  // Load initial status
  useEffect((): void => {
    const loadStatus = async (): Promise<void> => {
      try {
        const status = await getStatus();
        setEnabledState(status.enabled);
        setWatcherRunning(status.watcher_running);
        setEdRunning(status.ed_running);
        setJournalPath(status.journal_path);
        setJournalPathSource(status.journal_path_source);
        setTargets(status.targets);
        const uid = status.uploader_id;
        setUploaderIdState(uid);
        setUploaderIdInput(uid);
        uploaderIdRef.current = uid;
        setEdsmCommanderInput(status.edsm_commander_name);
        setEdsmApiKeySet(status.edsm_api_key_set);
        setEdsmLookupsEnabledState(status.edsm_lookups_enabled);
        setEdsmWorthScanning(status.edsm_worth_scanning);
        setDetailedLoggingState(status.detailed_logging);
      } catch (e) {
        console.error("Failed to load status", e);
      }
    };
    void loadStatus();

    // Rehydrate session stats so the panel shows the current launch immediately.
    const loadSessionStats = async (): Promise<void> => {
      try {
        setSessionStats(await getSessionStats());
      } catch (e) {
        console.error("Failed to load session stats", e);
      }
    };
    void loadSessionStats();
  }, []);

  // Listen for backend events
  useEffect((): (() => void) => {
    const statusListener = addEventListener("status_update", (data: StatusUpdateEvent): void => {
      // Full per-target snapshot (reset, EDSM batch completion).
      setTargets(data.targets);
    });

    const edStateListener = addEventListener("ed_state_change", (data: EdStateChangeEvent): void => {
      setEdRunning(data.ed_running);
      if (!data.ed_running) {
        setEdsmWorthScanning(null);
      }
    });

    const worthScanningListener = addEventListener("edsm_worth_scanning", (data: EdsmWorthScanningEvent): void => {
      if (data.verdict === null) {
        setEdsmWorthScanning(null);
      } else {
        setEdsmWorthScanning(data);
      }
    });

    const sessionListener = addEventListener("session_update", (data: SessionUpdateEvent): void => {
      setSessionStats(data);
    });

    // EDDN per-event totals update the "eddn" target entry in place.
    const successListener = addEventListener("upload_success", (data: UploadSuccessEvent): void => {
      setTargets((prev): TargetStatsMap => {
        const eddn = readTarget(prev, "eddn") ?? { success_count: 0, fail_count: 0 };
        return { ...prev, eddn: { ...eddn, success_count: data.total_success } };
      });
    });

    const failListener = addEventListener("upload_failed", (data: UploadFailedEvent): void => {
      setTargets((prev): TargetStatsMap => {
        const eddn = readTarget(prev, "eddn") ?? { success_count: 0, fail_count: 0 };
        return { ...prev, eddn: { ...eddn, fail_count: data.total_failed } };
      });
    });

    const activityListener = addEventListener("activity_update", (entry: ActivityEntry): void => {
      // Add to recent activity (keep last 10)
      setRecentActivity((prev): ActivityEntry[] => {
        const updated = [entry, ...prev];
        return updated.slice(0, 10);
      });
      // Add to errors if failure (keep last 5)
      if (entry.outcome === "failure") {
        setRecentErrors((prev): ActivityEntry[] => {
          const updated = [entry, ...prev];
          return updated.slice(0, 5);
        });
      }
    });

    // Auto-detect commander name from LoadGame for uploader ID
    // Uses ref to check current value (avoids stale closure capturing initial "")
    const commanderListener = addEventListener("commander_detected", (data: { commander: string }): void => {
      if (data.commander && !uploaderIdRef.current) {
        void (async (): Promise<void> => {
          await setUploaderId(data.commander);
          setUploaderIdState(data.commander);
          setUploaderIdInput(data.commander);
          uploaderIdRef.current = data.commander;
        })();
      }
    });

    // Fetch initial activity
    void (async (): Promise<void> => {
      try {
        const activity = await getRecentActivity(10);
        setRecentActivity(activity);
        const errors = await getRecentActivity(5, "failure");
        setRecentErrors(errors);
      } catch (e) {
        console.error("Failed to fetch activity", e);
      }
    })();

    return (): void => {
      removeEventListener("status_update", statusListener);
      removeEventListener("ed_state_change", edStateListener);
      removeEventListener("session_update", sessionListener);
      removeEventListener("upload_success", successListener);
      removeEventListener("upload_failed", failListener);
      removeEventListener("activity_update", activityListener);
      removeEventListener("commander_detected", commanderListener);
      removeEventListener("edsm_worth_scanning", worthScanningListener);
    };
  }, []);

  const handleToggle = async (state: boolean): Promise<void> => {
    await setEnabled(state);
    setEnabledState(state);
    if (state) {
      // Re-check if ED is running and start watcher
      const status = await getStatus();
      if (status.journal_path) {
        await startWatcher();
        setWatcherRunning(true);
      }
    } else {
      await stopWatcher();
      setWatcherRunning(false);
    }
  };

  const handleSetManualPath = async (): Promise<void> => {
    setPathError(null);
    const result = await setManualJournalPath(manualPathInput);
    if (result.success) {
      setJournalPath(manualPathInput);
      setJournalPathSource("manual");
      setManualPathInput("");
    } else {
      setPathError(result.error ?? "Invalid path");
    }
  };

  const handleSetUploaderId = async (): Promise<void> => {
    await setUploaderId(uploaderIdInput);
    setUploaderIdState(uploaderIdInput);
    uploaderIdRef.current = uploaderIdInput;
  };

  const handleSetEdsmCredentials = async (): Promise<void> => {
    await setEdsmCredentials(edsmCommanderInput, edsmApiKeyInput);
    // A key is now saved if one was just entered, or one was already saved.
    setEdsmApiKeySet((prev): boolean => prev || edsmApiKeyInput.length > 0);
    setEdsmApiKeyInput("");
    setEdsmSaved(true);
  };

  const handleRescan = async (): Promise<void> => {
    const result = await findJournalPath();
    if (result.success) {
      setJournalPath(result.path ?? null);
      setJournalPathSource("auto");
    }
  };

  const handleDetailedLoggingToggle = async (state: boolean): Promise<void> => {
    await setDetailedLogging(state);
    setDetailedLoggingState(state);
  };

  const handleEdsmLookupsToggle = async (state: boolean): Promise<void> => {
    await setEdsmLookupsEnabled(state);
    setEdsmLookupsEnabledState(state);
    if (!state) {
      setEdsmWorthScanning(null);
    }
  };

  const formatCredits = (value: number): string => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
    return String(value);
  };

  // Renders only when a value fetch has actually succeeded (totalValue !== null).
  // When it hasn't (disabled, in-flight, or a contained failure), rendering
  // nothing is the neutral state — consistent with the worth-scanning chip,
  // which disappears the same way.
  const getSystemValueDisplay = (): JSX.Element | null => {
    if (!edsmWorthScanning || edsmWorthScanning.totalValue === null) return null;
    const { totalValue, priorityBodies } = edsmWorthScanning;
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        <span style={{ fontSize: "12px" }}>
          <strong>{formatCredits(totalValue)} CR</strong>
          <span style={{ opacity: 0.6 }}> est. scan value</span>
        </span>
        {priorityBodies.length > 0 && (
          <span style={{ fontSize: "11px", opacity: 0.8, overflowWrap: "anywhere" }}>
            {priorityBodies.map((b): string => `${b.name} (${formatCredits(b.value)})`).join(", ")}
          </span>
        )}
      </div>
    );
  };

  const getWorthScanningChip = (): JSX.Element | null => {
    if (!edsmWorthScanning) return null;
    const { verdict } = edsmWorthScanning;
    const colour = verdict === "green" ? "#4CAF50" : verdict === "yellow" ? "#FFC107" : verdict === "red" ? "#f44336" : "#888";
    const label = verdict === "green" ? "Worth scanning" : verdict === "yellow" ? "Partially explored" : verdict === "red" ? "Fully explored" : "Checking…";
    return (
      <span style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "12px",
        backgroundColor: colour,
        color: "#fff",
        fontSize: "11px",
        fontWeight: "bold",
        letterSpacing: "0.3px",
      }}>
        {label} · EDSM
      </span>
    );
  };

  const handleCreateDiagnostics = async (): Promise<void> => {
    const result = await createDiagnosticsBundle();
    setDiagnosticResult(result);
  };

  const getEdStatusText = (): string => {
    return edRunning ? "🟢 Running" : "⚪ Not Running";
  };

  const getEdsmStatusText = (): string => {
    if (!edsmApiKeySet) return "⚪ Inactive — no API key set";
    const edsmActive = readTarget(targets, "edsm")?.active ?? false;
    if (edsmActive) return "🟢 Active — forwarding this session";
    return edRunning
      ? "🟡 Enabled — starting…"
      : "🟡 Enabled — starts when Elite Dangerous launches";
  };

  const getJournalStatusText = (): string => {
    if (!journalPath) return "🔍 Not Found";
    if (watcherRunning) return "🟢 Watching";
    // Journal path found but not watching
    return edRunning ? "⚠️ Found, Not Watching" : "📂 Found";
  };

  const getActivityKey = (entry: ActivityEntry): string => {
    const status = entry.http_status != null ? String(entry.http_status) : "na";
    return `${entry.timestamp}-${entry.event_type}-${entry.target}-${entry.outcome}-${status}`;
  };

  const hasSessionData = (s: SessionStats | null): boolean => {
    if (!s) return false;
    return (
      s.star_system !== "" ||
      s.jumps > 0 ||
      s.bodies_scanned > 0 ||
      s.first_discoveries > 0 ||
      s.distance_ly > 0
    );
  };

  const renderCounter = (label: string, value: string): JSX.Element => (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: "1 1 45%", padding: "4px 0" }}>
      <span style={{ fontSize: "20px", fontWeight: "bold", lineHeight: "1.1" }}>{value}</span>
      <span style={{ fontSize: "11px", opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</span>
    </div>
  );

  const formatTargetLabel = (key: string): string => key.toUpperCase();

  const renderUploadTargets = (): JSX.Element => {
    const entries = Object.entries(targets);
    if (entries.length === 0) {
      return (
        <PanelSectionRow>
          <Field label="Uploads">No uploads yet</Field>
        </PanelSectionRow>
      );
    }
    return (
      <>
        {entries.map(([key, stats]: [string, TargetStats]): JSX.Element => (
          <PanelSectionRow key={key}>
            <Field label={formatTargetLabel(key)}>
              ✅ {stats.success_count} ❌ {stats.fail_count}
            </Field>
          </PanelSectionRow>
        ))}
      </>
    );
  };

  const renderSession = (): JSX.Element => {
    if (!hasSessionData(sessionStats) || !sessionStats) {
      return (
        <PanelSectionRow>
          <Field>No session activity yet</Field>
        </PanelSectionRow>
      );
    }
    return (
      <>
        <PanelSectionRow>
          <div style={{ display: "flex", flexWrap: "wrap", width: "100%" }}>
            {renderCounter("Jumps", String(sessionStats.jumps))}
            {renderCounter("Distance (ly)", sessionStats.distance_ly.toFixed(1))}
            {renderCounter("Bodies Scanned", String(sessionStats.bodies_scanned))}
            {renderCounter("First Discoveries", String(sessionStats.first_discoveries))}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ width: "100%", borderTop: "1px solid rgba(255,255,255,0.1)", margin: "4px 0" }} />
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "4px" }}>
            <span style={{ fontSize: "11px", opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.5px" }}>Current location</span>
            <span style={{ fontSize: "16px", fontWeight: "bold", overflowWrap: "anywhere" }}>
              {sessionStats.star_system || "Unknown"}
            </span>
            {getWorthScanningChip()}
            {getSystemValueDisplay()}
          </div>
        </PanelSectionRow>
      </>
    );
  };

  return (
    <div>
      <PanelSection title="Session">
        {renderSession()}
      </PanelSection>

      <PanelSection title="Status">
        <PanelSectionRow>
          <ToggleField
            label="Watch journal"
            checked={enabled}
            onChange={(state: boolean): void => { void handleToggle(state); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Enable EDSM lookup"
            checked={edsmLookupsEnabled}
            onChange={(state: boolean): void => { void handleEdsmLookupsToggle(state); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="ED Status">
            {getEdStatusText()}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Journal Status">
            {getJournalStatusText()}
          </Field>
        </PanelSectionRow>
        {renderUploadTargets()}
      </PanelSection>

      <PanelSection title="Recent Activity">
        {recentActivity.length === 0 ? (
          <PanelSectionRow>
            <Field>No activity yet</Field>
          </PanelSectionRow>
        ) : (
          recentActivity.map((entry: ActivityEntry): JSX.Element => (
            <PanelSectionRow key={getActivityKey(entry)}>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span>
                  {entry.outcome === "success" ? "✅" : "❌"} {entry.event_type}
                  <span style={{ fontSize: "11px", opacity: 0.6 }}> · {formatTargetLabel(entry.target)}</span>
                </span>
                <span style={{ fontSize: "12px", opacity: 0.7 }}>{new Date(entry.timestamp).toLocaleTimeString()}</span>
              </div>
            </PanelSectionRow>
          ))
        )}
      </PanelSection>

      <PanelSection title="Configuration">
        {journalPath && (
          <PanelSectionRow>
            <Field label="Journal Path">
              {journalPath.length > 40 ? journalPath.slice(0, 18) + '…' + journalPath.slice(-18) : journalPath}
            </Field>
          </PanelSectionRow>
        )}
        {journalPathSource && (
          <PanelSectionRow>
            <Field label="Path Source">
              {journalPathSource === "auto" ? "Auto-detected" : "Manual"}
            </Field>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={(): void => { void handleRescan(); }}>
            Re-scan for Journal Path
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Manual Journal Path"
            value={manualPathInput}
            onChange={(e): void => { setManualPathInput(e.target.value); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={(): void => { void handleSetManualPath(); }} disabled={!manualPathInput}>
            Set Manual Path
          </ButtonItem>
        </PanelSectionRow>
        {pathError && (
          <PanelSectionRow>
            <Field>
              ⚠️ {pathError}
            </Field>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <TextField
            label="EDDN Uploader ID"
            value={uploaderIdInput}
            onChange={(e): void => { setUploaderIdInput(e.target.value); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={(): void => { void handleSetUploaderId(); }} disabled={!uploaderIdInput}>
            Save Uploader ID
          </ButtonItem>
        </PanelSectionRow>
        {!uploaderId && (
          <PanelSectionRow>
            <Field>
              ⚠️ Uploader ID will be auto-set from your CMDR name when ED loads a game session
            </Field>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="EDSM">
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: "12px", opacity: 0.8, textAlign: "justify" }}>
            EDSM uploads your flight logs under your <strong>named EDSM identity</strong>,
            unlike anonymous EDDN. It is off until you enter an API key.
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Status">
            {getEdsmStatusText()}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="EDSM Commander Name"
            value={edsmCommanderInput}
            onChange={(e): void => { setEdsmCommanderInput(e.target.value); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={edsmApiKeySet ? "EDSM API Key (saved — leave blank to keep)" : "EDSM API Key"}
            value={edsmApiKeyInput}
            onChange={(e): void => {
              setEdsmApiKeyInput(e.target.value);
              setEdsmSaved(false);
            }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={(): void => { void handleSetEdsmCredentials(); }}
            disabled={!edsmCommanderInput || (!edsmApiKeyInput && !edsmApiKeySet)}
          >
            Save EDSM Credentials
          </ButtonItem>
        </PanelSectionRow>
        {edsmSaved && (
          <PanelSectionRow>
            <div style={{ width: "100%", fontSize: "12px", textAlign: "left" }}>
              ✅ Saved
            </div>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <div style={{ width: "100%", fontSize: "12px", opacity: 0.7, textAlign: "left", overflowWrap: "anywhere" }}>
            Generate your API key at {EDSM_API_KEY_URL}
          </div>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Recent Errors">
        {recentErrors.length === 0 ? (
          <PanelSectionRow>
            <Field>No errors</Field>
          </PanelSectionRow>
        ) : (
          recentErrors.map((entry: ActivityEntry): JSX.Element => (
            <PanelSectionRow key={getActivityKey(entry)}>
              <Field label={`${entry.event_type} · ${formatTargetLabel(entry.target)}`}>
                <div style={{ fontSize: "12px" }}>
                  <div>{new Date(entry.timestamp).toLocaleTimeString()} — {entry.error_type}</div>
                  <div>{entry.error_message}{entry.http_status != null ? ` (${String(entry.http_status)})` : ""}</div>
                </div>
              </Field>
            </PanelSectionRow>
          ))
        )}
      </PanelSection>

      <PanelSection title="Diagnostics">
        <PanelSectionRow>
          <ToggleField
            label="Detailed Logging"
            description="Enables DEBUG-level logging for richer diagnostic output"
            checked={detailedLogging}
            onChange={(state: boolean): void => { void handleDetailedLoggingToggle(state); }}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={(): void => { void handleCreateDiagnostics(); }}>
            Create Diagnostic Bundle
          </ButtonItem>
        </PanelSectionRow>
        {diagnosticResult && (
          <PanelSectionRow>
            <Field label="Bundle">
              {diagnosticResult.success
                ? `✅ ${diagnosticResult.path ?? ""} (${String(Math.round((diagnosticResult.size ?? 0) / 1024))} KB)`
                : `❌ ${diagnosticResult.error ?? "Unknown error"}`}
            </Field>
          </PanelSectionRow>
        )}
      </PanelSection>
    </div>
  );
};

export default Content;
