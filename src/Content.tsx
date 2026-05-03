import { useState, useEffect } from "react";
import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
  Field,
  ButtonItem,
  TextField,
} from "@decky/ui";
import { callable, addEventListener, removeEventListener } from "@decky/api";
import type { JSX } from "react";

// Backend callables
const getStatus = callable<[], GetStatusResult>("get_status");
const startWatcher = callable<[], Record<string, unknown>>("start_watcher");
const stopWatcher = callable<[], Record<string, unknown>>("stop_watcher");
const findJournalPath = callable<[], FindPathResult>("find_journal_path");
const setManualJournalPath = callable<[string], SetManualPathResult>("set_journal_path");
const setEnabled = callable<[boolean], Record<string, unknown>>("set_enabled");
const setUploaderId = callable<[string], Record<string, unknown>>("set_uploader_id");

const Content = (): JSX.Element => {
  const [enabled, setEnabledState] = useState(true);
  const [watcherRunning, setWatcherRunning] = useState(false);
  const [journalPath, setJournalPath] = useState<string | null>(null);
  const [journalPathSource, setJournalPathSource] = useState<string | null>(null);
  const [successCount, setSuccessCount] = useState(0);
  const [failCount, setFailCount] = useState(0);
  const [lastUpload, setLastUpload] = useState<string | null>(null);
  const [uploaderId, setUploaderIdState] = useState<string>("");
  const [manualPathInput, setManualPathInput] = useState<string>("");
  const [uploaderIdInput, setUploaderIdInput] = useState<string>("");
  const [pathError, setPathError] = useState<string | null>(null);

  // Load initial status
  useEffect((): void => {
    const loadStatus = async (): Promise<void> => {
      try {
        const status = await getStatus();
        setEnabledState(status.enabled);
        setWatcherRunning(status.watcher_running);
        setJournalPath(status.journal_path);
        setJournalPathSource(status.journal_path_source);
        setSuccessCount(status.success_count);
        setFailCount(status.fail_count);
        setLastUpload(status.last_upload_time);
        const uid = status.uploader_id;
        setUploaderIdState(uid);
        setUploaderIdInput(uid);
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
      setLastUpload(data.last_upload_time);
    });

    const successListener = addEventListener("upload_success", (data: UploadSuccessEvent): void => {
      setSuccessCount(data.total_success);
    });

    const failListener = addEventListener("upload_failed", (data: UploadFailedEvent): void => {
      setFailCount(data.total_failed);
    });

    return (): void => {
      removeEventListener("status_update", statusListener);
      removeEventListener("upload_success", successListener);
      removeEventListener("upload_failed", failListener);
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
  };

  const handleRescan = async (): Promise<void> => {
    const result = await findJournalPath();
    if (result.success) {
      setJournalPath(result.path ?? null);
      setJournalPathSource("auto");
    }
  };

  const getStatusText = (): string => {
    if (!enabled) return "⚪ Disabled";
    if (!journalPath) return "🔍 Journal path not found";
    if (watcherRunning) return "🟢 Watching — uploading journal events";
    return "⚪ Idle — waiting for Elite Dangerous";
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
          <Field label="Status">
            {getStatusText()}
          </Field>
        </PanelSectionRow>
        <PanelSectionRow>
          <Field label="Uploads">
            ✅ {successCount} ❌ {failCount}
          </Field>
        </PanelSectionRow>
        {lastUpload && (
          <PanelSectionRow>
            <Field label="Last Upload">
              {new Date(lastUpload).toLocaleTimeString()}
            </Field>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Configuration">
        {journalPath && (
          <PanelSectionRow>
            <Field label="Journal Path">
              {journalPath}
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
              ⚠️ Set an uploader ID before uploading
            </Field>
          </PanelSectionRow>
        )}
      </PanelSection>
    </div>
  );
};

export default Content;
