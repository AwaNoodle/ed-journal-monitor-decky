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
  getStatus,
  setDetailedLogging,
  setEnabled,
  setManualJournalPath,
  setUploaderId,
  startWatcher,
  stopWatcher,
} from "./api";

const Content = (): JSX.Element => {
  const [enabled, setEnabledState] = useState(true);
  const [watcherRunning, setWatcherRunning] = useState(false);
  const [edRunning, setEdRunning] = useState(false);
  const [journalPath, setJournalPath] = useState<string | null>(null);
  const [journalPathSource, setJournalPathSource] = useState<string | null>(null);
  const [successCount, setSuccessCount] = useState(0);
  const [failCount, setFailCount] = useState(0);
  const [uploaderId, setUploaderIdState] = useState<string>("");
  const [manualPathInput, setManualPathInput] = useState<string>("");
  const [uploaderIdInput, setUploaderIdInput] = useState<string>("");
  const [pathError, setPathError] = useState<string | null>(null);
  const [detailedLogging, setDetailedLoggingState] = useState(false);
  const [diagnosticResult, setDiagnosticResult] = useState<DiagnosticsResult | null>(null);
  const [recentErrors, setRecentErrors] = useState<ActivityEntry[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityEntry[]>([]);

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
        setSuccessCount(status.success_count);
        setFailCount(status.fail_count);
        const uid = status.uploader_id;
        setUploaderIdState(uid);
        setUploaderIdInput(uid);
        uploaderIdRef.current = uid;
        setDetailedLoggingState(status.detailed_logging);
      } catch (e) {
        console.error("Failed to load status", e);
      }
    };
    void loadStatus();
  }, []);

  // Listen for backend events
  useEffect((): (() => void) => {
    const statusListener = addEventListener("status_update", (data: StatusUpdateEvent): void => {
      setSuccessCount(data.success_count);
      setFailCount(data.fail_count);
    });

    const edStateListener = addEventListener("ed_state_change", (data: EdStateChangeEvent): void => {
      setEdRunning(data.ed_running);
    });

    const successListener = addEventListener("upload_success", (data: UploadSuccessEvent): void => {
      setSuccessCount(data.total_success);
    });

    const failListener = addEventListener("upload_failed", (data: UploadFailedEvent): void => {
      setFailCount(data.total_failed);
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
      removeEventListener("upload_success", successListener);
      removeEventListener("upload_failed", failListener);
      removeEventListener("activity_update", activityListener);
      removeEventListener("commander_detected", commanderListener);
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

  const handleCreateDiagnostics = async (): Promise<void> => {
    const result = await createDiagnosticsBundle();
    setDiagnosticResult(result);
  };

  const getEdStatusText = (): string => {
    return edRunning ? "🟢 Running" : "⚪ Not Running";
  };

  const getJournalStatusText = (): string => {
    if (!journalPath) return "🔍 Not Found";
    if (watcherRunning) return "🟢 Watching";
    // Journal path found but not watching
    return edRunning ? "⚠️ Found, Not Watching" : "📂 Found";
  };

  const getActivityKey = (entry: ActivityEntry): string => {
    const status = entry.http_status != null ? String(entry.http_status) : "na";
    return `${entry.timestamp}-${entry.event_type}-${entry.outcome}-${status}`;
  };

  return (
    <div>
      <PanelSection title="Status">
        <PanelSectionRow>
          <ToggleField
            label="Enabled"
            checked={enabled}
            onChange={(state: boolean): void => { void handleToggle(state); }}
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
        <PanelSectionRow>
          <Field label="Uploads">
            ✅ {successCount} ❌ {failCount}
          </Field>
        </PanelSectionRow>
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
                <span>{entry.outcome === "success" ? "✅" : "❌"} {entry.event_type}</span>
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

      <PanelSection title="Recent Errors">
        {recentErrors.length === 0 ? (
          <PanelSectionRow>
            <Field>No errors</Field>
          </PanelSectionRow>
        ) : (
          recentErrors.map((entry: ActivityEntry): JSX.Element => (
            <PanelSectionRow key={getActivityKey(entry)}>
              <Field label={entry.event_type}>
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
