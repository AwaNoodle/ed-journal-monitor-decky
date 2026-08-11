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
import type { JSX, ReactNode } from "react";
import {
  createDiagnosticsBundle,
  findJournalPath,
  getNearestScoopableStar,
  getRecentActivity,
  getSessionStats,
  getStatus,
  setDetailedLogging,
  setEdsmCredentials,
  setEdsmLookupsEnabled,
  setEdsmNotificationsEnabled,
  setEdsmNotifyAllVerdicts,
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

// --- Collapsible section primitive ---------------------------------------
// Built from Field (@decky/ui ships no collapsible). Collapsed children are
// not rendered (never CSS-hidden), so they contribute no gamepad focus stops.
// The header Field is the single focusable toggle; the chevron icon shows
// expanded/collapsed state.
const CollapsibleSection = ({
  label, summary, expanded, onToggle, indentLevel, children,
}: {
  label: string;
  summary?: ReactNode;
  expanded: boolean;
  onToggle: () => void;
  indentLevel?: number;
  children: ReactNode;
}): JSX.Element => (
  <>
    <PanelSectionRow>
      <Field
        focusable
        onActivate={onToggle}
        label={label}
        icon={<span aria-hidden>{expanded ? "▾" : "▸"}</span>}
        indentLevel={indentLevel}
      >
        {summary}
      </Field>
    </PanelSectionRow>
    {expanded && children}
  </>
);

// --- Health strip -----------------------------------------------------------
// A single always-visible, non-focusable line replacing the old separate
// ED Status / Journal Status fields. Worst-state-wins.
type HealthState = "no_path" | "running_not_watching" | "paused" | "waiting" | "watching";

const healthState = (
  journalPath: string | null,
  edRunning: boolean,
  watcherRunning: boolean,
  enabled: boolean,
): HealthState => {
  if (!journalPath) return "no_path";
  if (edRunning && !watcherRunning) return "running_not_watching";
  if (!enabled) return "paused";
  if (!edRunning) return "waiting";
  return "watching";
};

const HEALTH_STRIP_TEXT: Record<HealthState, string> = {
  no_path: "🔍 No journal path configured — see Setup",
  running_not_watching: "⚠️ Elite Dangerous is running, but the plugin isn't watching",
  paused: "⏸️ Watching paused",
  waiting: "🟡 Ready — waiting for Elite Dangerous",
  watching: "🟢 Watching",
};

const NEXT_HOP_REASON_TEXT: Record<string, string> = {
  no_route: "No route plotted",
  final_hop: "Destination reached",
  off_route: "Off the plotted route",
  disabled: "Enable EDSM lookups to preview the next hop",
};

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
  const [recentActivity, setRecentActivity] = useState<ActivityEntry[]>([]);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [edsmLookupsEnabled, setEdsmLookupsEnabledState] = useState<boolean>(false);
  const [edsmNotificationsEnabled, setEdsmNotificationsEnabledState] = useState<boolean>(false);
  const [edsmNotifyAllVerdicts, setEdsmNotifyAllVerdictsState] = useState<boolean>(false);
  const [edsmWorthScanning, setEdsmWorthScanning] = useState<EdsmWorthScanningVerdict | null>(null);
  const [edsmNextHop, setEdsmNextHop] = useState<EdsmNextHopPreview | null>(null);
  const [nearestScoopable, setNearestScoopable] = useState<NearestScoopableStarResult | null>(null);
  const [nearestScoopableLoading, setNearestScoopableLoading] = useState<boolean>(false);

  // Collapse state resets on every panel open — plain useState is enough
  // since Content unmounts when the panel closes.
  const [dataFlowExpanded, setDataFlowExpanded] = useState(false);
  const [setupExpanded, setSetupExpanded] = useState(false);
  const [troubleshootingExpanded, setTroubleshootingExpanded] = useState(false);
  const [journalGroupExpanded, setJournalGroupExpanded] = useState(false);
  const [eddnGroupExpanded, setEddnGroupExpanded] = useState(false);
  const [edsmAccountGroupExpanded, setEdsmAccountGroupExpanded] = useState(false);
  const [edsmLookupsGroupExpanded, setEdsmLookupsGroupExpanded] = useState(false);

  // Ref to track current uploaderId so the commander_detected listener
  // doesn't use a stale closure value
  const uploaderIdRef = useRef<string>("");
  // Data flow's initial expanded state is derived once from the failure
  // count at load time, not re-evaluated live (a failure arriving mid-session
  // should not yank the section open under the player's hands).
  const dataFlowAutoExpandChecked = useRef<boolean>(false);

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
        if (!dataFlowAutoExpandChecked.current) {
          dataFlowAutoExpandChecked.current = true;
          const failCount = Object.values(status.targets).reduce((sum, t): number => sum + t.fail_count, 0);
          if (failCount > 0) setDataFlowExpanded(true);
        }
        const uid = status.uploader_id;
        setUploaderIdState(uid);
        setUploaderIdInput(uid);
        uploaderIdRef.current = uid;
        setEdsmCommanderInput(status.edsm_commander_name);
        setEdsmApiKeySet(status.edsm_api_key_set);
        setEdsmLookupsEnabledState(status.edsm_lookups_enabled);
        setEdsmNotificationsEnabledState(status.edsm_notifications_enabled);
        setEdsmNotifyAllVerdictsState(status.edsm_notify_all_verdicts);
        setEdsmWorthScanning(status.edsm_worth_scanning);
        setEdsmNextHop(status.edsm_next_hop);
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
        setEdsmNextHop(null);
        setNearestScoopable(null);
      }
    });

    const worthScanningListener = addEventListener("edsm_worth_scanning", (data: EdsmWorthScanningEvent): void => {
      if (data.verdict === null) {
        setEdsmWorthScanning(null);
      } else {
        setEdsmWorthScanning(data);
      }
    });

    const nextHopListener = addEventListener("edsm_next_hop", (data: EdsmNextHopEvent): void => {
      setEdsmNextHop(data);
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
      // Add to the merged feed (keep last 10)
      setRecentActivity((prev): ActivityEntry[] => {
        const updated = [entry, ...prev];
        return updated.slice(0, 10);
      });
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
        setRecentActivity(await getRecentActivity(10));
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
      removeEventListener("edsm_next_hop", nextHopListener);
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
      setEdsmNextHop(null);
      setNearestScoopable(null);
    }
  };

  const handleEdsmNotificationsToggle = async (state: boolean): Promise<void> => {
    await setEdsmNotificationsEnabled(state);
    setEdsmNotificationsEnabledState(state);
  };

  const handleEdsmNotifyAllVerdictsToggle = async (state: boolean): Promise<void> => {
    await setEdsmNotifyAllVerdicts(state);
    setEdsmNotifyAllVerdictsState(state);
  };

  // Self-enabling: when lookups are off, one activation persists the setting
  // and then runs the search — no dead-end advisory text.
  const handleFindNearestScoopable = async (): Promise<void> => {
    setNearestScoopableLoading(true);
    try {
      if (!edsmLookupsEnabled) {
        await setEdsmLookupsEnabled(true);
        setEdsmLookupsEnabledState(true);
      }
      setNearestScoopable(await getNearestScoopableStar());
    } finally {
      setNearestScoopableLoading(false);
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
  // which disappears the same way. Shared by the Current location and Next hop
  // blocks.
  const renderSystemValue = (
    data: { totalValue: number | null; priorityBodies: EdsmPriorityBody[] } | null,
  ): JSX.Element | null => {
    if (!data || data.totalValue === null) return null;
    const { totalValue, priorityBodies } = data;
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

  // Coloured worth-scanning pill (EDSM-attributed). Shared by both blocks.
  const renderVerdictChip = (verdict: "green" | "yellow" | "red" | null): JSX.Element => {
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

  // Scoopability pill: green when scoopable, red when not; nothing when unknown.
  const renderScoopChip = (scoopable: boolean | null): JSX.Element | null => {
    if (scoopable === null) return null;
    const colour = scoopable ? "#4CAF50" : "#f44336";
    const label = scoopable ? "⛽ Scoopable" : "🚱 Not scoopable";
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
        {label}
      </span>
    );
  };

  // Next-in-route preview: rendered in every state (permanent block, fixed
  // minimum footprint) rather than hidden when there is no next hop. Branches
  // on `reason`; falls back to generic no-route text when it is absent
  // (payload from a not-yet-updated backend).
  const renderNextHop = (): JSX.Element => {
    const reasonText = edsmNextHop?.reason ? NEXT_HOP_REASON_TEXT[edsmNextHop.reason] : undefined;
    return (
      <PanelSectionRow>
        <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "4px", minHeight: "60px" }}>
          <span style={{ fontSize: "11px", opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.5px" }}>Next hop · EDSM</span>
          {edsmNextHop && edsmNextHop.system !== null ? (
            <>
              <span style={{ fontSize: "16px", fontWeight: "bold", overflowWrap: "anywhere" }}>
                {edsmNextHop.system}
              </span>
              {edsmNextHop.verdict !== null && renderVerdictChip(edsmNextHop.verdict)}
              {renderSystemValue(edsmNextHop)}
              {renderScoopChip(edsmNextHop.scoopable)}
            </>
          ) : (
            <span style={{ fontSize: "13px", opacity: 0.7 }}>
              {reasonText ?? NEXT_HOP_REASON_TEXT.no_route}
            </span>
          )}
        </div>
      </PanelSectionRow>
    );
  };

  // Result of the on-demand nearest-scoopable-star lookup.
  const renderNearestScoopableResult = (): JSX.Element | null => {
    if (!nearestScoopable) return null;
    if (nearestScoopable.status === "ok") {
      return (
        <PanelSectionRow>
          <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "4px" }}>
            <span style={{ fontSize: "11px", opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Nearest scoopable star · EDSM
            </span>
            <span style={{ fontSize: "16px", fontWeight: "bold", overflowWrap: "anywhere" }}>
              {nearestScoopable.system}
            </span>
            <span style={{ fontSize: "12px", opacity: 0.8 }}>
              {nearestScoopable.distance?.toFixed(2)} ly · {nearestScoopable.star_class}
            </span>
          </div>
        </PanelSectionRow>
      );
    }
    if (nearestScoopable.status === "none_found") {
      return (
        <PanelSectionRow>
          <Field>⛽ No scoopable star found within the search radius</Field>
        </PanelSectionRow>
      );
    }
    if (nearestScoopable.status === "unavailable") {
      return (
        <PanelSectionRow>
          <Field>⚠️ Lookup unavailable — try again</Field>
        </PanelSectionRow>
      );
    }
    return null;
  };

  // On-demand "help me now" action: finds the nearest fuel-scoopable star from
  // the current system via an EDSM sphere-systems query. Self-enabling: if
  // auto-lookups are off, one activation turns them on and runs the search.
  const renderNearestScoopable = (): JSX.Element => (
    <>
      <PanelSectionRow>
        <div style={{ width: "100%", borderTop: "1px solid rgba(255,255,255,0.1)", margin: "4px 0" }} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={(): void => { void handleFindNearestScoopable(); }}
          disabled={nearestScoopableLoading}
        >
          {nearestScoopableLoading
            ? "Searching…"
            : edsmLookupsEnabled
              ? "Find Nearest Scoopable Star"
              : "Enable EDSM lookups to search"}
        </ButtonItem>
      </PanelSectionRow>
      {renderNearestScoopableResult()}
    </>
  );

  const getEdsmStatusText = (): string => {
    if (!edsmApiKeySet) return "⚪ Inactive — no API key set";
    const edsmActive = readTarget(targets, "edsm")?.active ?? false;
    if (edsmActive) return "🟢 Active — forwarding this session";
    return edRunning
      ? "🟡 Enabled — starting…"
      : "🟡 Enabled — starts when Elite Dangerous launches";
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

  // Navigation: the always-visible, non-collapsible flight view — current
  // location, worth-scanning verdict, system value, the permanent next-hop
  // block, and the on-demand nearest-scoopable action.
  const renderNavigation = (): JSX.Element => (
    <>
      <PanelSectionRow>
        <div style={{ display: "flex", flexDirection: "column", width: "100%", gap: "4px" }}>
          <span style={{ fontSize: "11px", opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.5px" }}>Current location</span>
          <span style={{ fontSize: "16px", fontWeight: "bold", overflowWrap: "anywhere" }}>
            {sessionStats?.star_system || "Unknown"}
          </span>
          {edsmWorthScanning && renderVerdictChip(edsmWorthScanning.verdict)}
          {renderSystemValue(edsmWorthScanning)}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ width: "100%", borderTop: "1px solid rgba(255,255,255,0.1)", margin: "4px 0" }} />
      </PanelSectionRow>
      {renderNextHop()}
      {renderNearestScoopable()}
    </>
  );

  // Session: the counters only — current location moved to Navigation above it.
  const renderSessionCounters = (): JSX.Element => {
    if (!hasSessionData(sessionStats) || !sessionStats) {
      return (
        <PanelSectionRow>
          <Field>No session activity yet</Field>
        </PanelSectionRow>
      );
    }
    return (
      <PanelSectionRow>
        <div style={{ display: "flex", flexWrap: "wrap", width: "100%" }}>
          {renderCounter("Jumps", String(sessionStats.jumps))}
          {renderCounter("Distance (ly)", sessionStats.distance_ly.toFixed(1))}
          {renderCounter("Bodies Scanned", String(sessionStats.bodies_scanned))}
          {renderCounter("First Discoveries", String(sessionStats.first_discoveries))}
        </div>
      </PanelSectionRow>
    );
  };

  // Data flow: per-target counters plus the merged success/failure feed
  // (Recent Activity + Recent Errors combined — both are the same log,
  // filtered differently).
  const renderDataFlow = (): JSX.Element => (
    <>
      {renderUploadTargets()}
      <PanelSectionRow>
        <div style={{ width: "100%", borderTop: "1px solid rgba(255,255,255,0.1)", margin: "4px 0" }} />
      </PanelSectionRow>
      {recentActivity.length === 0 ? (
        <PanelSectionRow>
          <Field>No activity yet</Field>
        </PanelSectionRow>
      ) : (
        recentActivity.map((entry: ActivityEntry): JSX.Element => (
          <PanelSectionRow key={getActivityKey(entry)}>
            {entry.outcome === "success" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span>
                  ✅ {entry.event_type}
                  <span style={{ fontSize: "11px", opacity: 0.6 }}> · {formatTargetLabel(entry.target)}</span>
                </span>
                <span style={{ fontSize: "12px", opacity: 0.7 }}>{new Date(entry.timestamp).toLocaleTimeString()}</span>
              </div>
            ) : (
              <Field label={`❌ ${entry.event_type} · ${formatTargetLabel(entry.target)}`}>
                <div style={{ fontSize: "12px" }}>
                  <div>{new Date(entry.timestamp).toLocaleTimeString()} — {entry.error_type}</div>
                  <div>{entry.error_message}{entry.http_status != null ? ` (${String(entry.http_status)})` : ""}</div>
                </div>
              </Field>
            )}
          </PanelSectionRow>
        ))
      )}
    </>
  );

  const renderJournalPathGroup = (): JSX.Element => (
    <div style={{ paddingLeft: "12px" }}>
      <PanelSectionRow>
        <ToggleField
          label="Watch journal"
          checked={enabled}
          onChange={(state: boolean): void => { void handleToggle(state); }}
        />
      </PanelSectionRow>
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
    </div>
  );

  const renderEddnGroup = (): JSX.Element => (
    <div style={{ paddingLeft: "12px" }}>
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
    </div>
  );

  const renderEdsmAccountGroup = (): JSX.Element => (
    <div style={{ paddingLeft: "12px" }}>
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
    </div>
  );

  const renderEdsmLookupsGroup = (): JSX.Element => (
    <div style={{ paddingLeft: "12px" }}>
      <PanelSectionRow>
        <div style={{ width: "100%", fontSize: "12px", opacity: 0.8, textAlign: "justify" }}>
          Keyless, anonymous reads from EDSM's public data — independent of the EDSM account above.
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Enable EDSM lookup"
          checked={edsmLookupsEnabled}
          onChange={(state: boolean): void => { void handleEdsmLookupsToggle(state); }}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="'Worth-scanning' Notifications"
          description="Toast over the running game on arrival in a worth-scanning system"
          checked={edsmNotificationsEnabled}
          disabled={!edsmLookupsEnabled}
          onChange={(state: boolean): void => { void handleEdsmNotificationsToggle(state); }}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label="Notify on partially-explored systems too"
          checked={edsmNotifyAllVerdicts}
          disabled={!edsmLookupsEnabled}
          onChange={(state: boolean): void => { void handleEdsmNotifyAllVerdictsToggle(state); }}
        />
      </PanelSectionRow>
    </div>
  );

  const renderSetup = (): JSX.Element => (
    <>
      <CollapsibleSection
        label="Journal path"
        summary={journalPath ? "Path set" : "No path set"}
        expanded={journalGroupExpanded}
        onToggle={(): void => { setJournalGroupExpanded((e): boolean => !e); } }
        indentLevel={1}
      >
        {renderJournalPathGroup()}
      </CollapsibleSection>
      <CollapsibleSection
        label="EDDN"
        summary={uploaderId ? "ID set" : "No ID"}
        expanded={eddnGroupExpanded}
        onToggle={(): void => { setEddnGroupExpanded((e): boolean => !e); } }
        indentLevel={1}
      >
        {renderEddnGroup()}
      </CollapsibleSection>
      <CollapsibleSection
        label="EDSM account"
        summary={edsmApiKeySet ? "API key set" : "No API key"}
        expanded={edsmAccountGroupExpanded}
        onToggle={(): void => { setEdsmAccountGroupExpanded((e): boolean => !e); } }
        indentLevel={1}
      >
        {renderEdsmAccountGroup()}
      </CollapsibleSection>
      <CollapsibleSection
        label="EDSM lookups"
        summary={edsmLookupsEnabled ? "Lookups on" : "Lookups off"}
        expanded={edsmLookupsGroupExpanded}
        onToggle={(): void => { setEdsmLookupsGroupExpanded((e): boolean => !e); } }
        indentLevel={1}
      >
        {renderEdsmLookupsGroup()}
      </CollapsibleSection>
    </>
  );

  const renderTroubleshooting = (): JSX.Element => (
    <>
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
    </>
  );

  const handleCreateDiagnostics = async (): Promise<void> => {
    const result = await createDiagnosticsBundle();
    setDiagnosticResult(result);
  };

  const aggregateCounts = Object.values(targets).reduce(
    (acc, t): { success: number; fail: number } => ({
      success: acc.success + t.success_count,
      fail: acc.fail + t.fail_count,
    }),
    { success: 0, fail: 0 },
  );

  const currentHealthState = healthState(journalPath, edRunning, watcherRunning, enabled);

  return (
    <div>
      <div style={{ padding: "8px 16px 4px", fontSize: "13px", opacity: 0.9 }}>
        {HEALTH_STRIP_TEXT[currentHealthState]}
        {currentHealthState === "watching" && uploaderId ? ` · CMDR ${uploaderId}` : ""}
      </div>

      <PanelSection title="Navigation">
        {renderNavigation()}
      </PanelSection>

      <PanelSection title="Session">
        {renderSessionCounters()}
      </PanelSection>

      <PanelSection>
        <CollapsibleSection
          label="Data flow"
          summary={`✅ ${String(aggregateCounts.success)} ❌ ${String(aggregateCounts.fail)}`}
          expanded={dataFlowExpanded}
          onToggle={(): void => { setDataFlowExpanded((e): boolean => !e); } }
        >
          {renderDataFlow()}
        </CollapsibleSection>
      </PanelSection>

      <PanelSection>
        <CollapsibleSection
          label="Setup"
          summary={journalPath && uploaderId ? "Configured" : "Needs setup"}
          expanded={setupExpanded}
          onToggle={(): void => { setSetupExpanded((e): boolean => !e); } }
        >
          {renderSetup()}
        </CollapsibleSection>
      </PanelSection>

      <PanelSection>
        <CollapsibleSection
          label="Troubleshooting"
          summary={detailedLogging ? "Logging: DEBUG" : "Logging: INFO"}
          expanded={troubleshootingExpanded}
          onToggle={(): void => { setTroubleshootingExpanded((e): boolean => !e); } }
        >
          {renderTroubleshooting()}
        </CollapsibleSection>
      </PanelSection>
    </div>
  );
};

export default Content;
