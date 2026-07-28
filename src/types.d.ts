declare module "*.svg" {
  const content: string;
  export default content;
}

declare module "*.png" {
  const content: string;
  export default content;
}

declare module "*.jpg" {
  const content: string;
  export default content;
}

// Per-target upload statistics. Keyed by target name (e.g. "eddn", "edsm") so
// the UI renders by mapping over entries — no hardcoded per-target keys.
interface TargetStats {
  success_count: number;
  fail_count: number;
  last_msgnum?: number | null;
  last_msg?: string | null;
  active?: boolean;
  queued?: number;
}

type TargetStatsMap = Record<string, TargetStats>;

// Decky API event listener types
interface StatusUpdateEvent {
  targets: TargetStatsMap;
  last_upload_time: string | null;
  last_upload_event: string | null;
}

interface UploadSuccessEvent {
  event: string;
  event_name: string;
  total_success: number;
}

interface UploadFailedEvent {
  event: string;
  total_failed: number;
}

// Submission target an activity entry / stats map is attributed to. Extend this
// union (and the backend UploadTarget Literal) to add a target like Inara.
type UploadTarget = "eddn" | "edsm";

interface ActivityEntry {
  timestamp: string;
  event_type: string;
  target: UploadTarget;
  outcome: "success" | "failure";
  error_type: string | null;
  error_message: string | null;
  http_status: number | null;
}

interface BasicSuccessResult {
  success: boolean;
  error?: string;
}

interface StartWatcherResult {
  success: boolean;
  status?: string;
  error?: string;
  journal_path?: string;
}

interface StopWatcherResult {
  success: boolean;
  status?: string;
  error?: string;
}

interface SetEnabledResult {
  success: boolean;
  enabled?: boolean;
  error?: string;
}

type SetUploaderIdResult = BasicSuccessResult;

interface SetDetailedLoggingResult {
  success: boolean;
  detailed_logging?: boolean;
  error?: string;
}

interface SetManualPathResult {
  success: boolean;
  error?: string;
}

interface FindPathResult {
  success: boolean;
  path?: string;
}

// A single priority body from the EDSM system value summary (highest-value
// bodies first).
interface EdsmPriorityBody {
  name: string;
  value: number;
}

// Worth-scanning verdict for the current system, sourced from EDSM public data.
// null verdict = neutral (disabled, in-flight, or lookup failed).
// system is null when verdict is null (clear event emitted on ED stop / toggle-off).
// totalValue is the system's estimated scan-only value (a floor — excludes any
// mapping bonus); null when the value fetch is disabled, in-flight, or failed.
// priorityBodies is the ranked top-N highest-value bodies (empty when none).
interface EdsmWorthScanningVerdict {
  system: string | null;
  verdict: "green" | "yellow" | "red" | null;
  source: "edsm";
  totalValue: number | null;
  priorityBodies: EdsmPriorityBody[];
}

// Emitted as "edsm_worth_scanning" decky event on each arrival. notify is the
// backend's notification decision (persisted settings + verdict) — present
// only on the live event, never on the get_status-rehydrated verdict, so a
// status refresh can never replay a toast.
type EdsmWorthScanningEvent = EdsmWorthScanningVerdict & { notify?: boolean };

// Next-in-route hop preview for the next system in the plotted route.
// system is null in the neutral state (no route, no next hop, or disabled).
// scoopable is derived from the plotted route's primary-star class (fuel
// safety) and stays present even when the EDSM lookup is unavailable; it is
// null only when the star class is unknown. verdict/totalValue/priorityBodies
// come from the EDSM per-system read and are neutral (null/[]) when unavailable.
interface EdsmNextHopPreview {
  system: string | null;
  scoopable: boolean | null;
  starClass: string | null;
  verdict: "green" | "yellow" | "red" | null;
  source: "edsm";
  totalValue: number | null;
  priorityBodies: EdsmPriorityBody[];
}

// Emitted as "edsm_next_hop" decky event on route change / after each jump.
type EdsmNextHopEvent = EdsmNextHopPreview;

// Result of the on-demand "nearest scoopable star" lookup (get_nearest_scoopable_star).
// - "ok": system/distance/star_class are populated
// - "none_found": sphere query ran but no scoopable star was within the radius
//   (also covers the current system being unknown to EDSM — no data to search)
// - "unavailable": the query failed (network/timeout) or the current system isn't known yet
// - "disabled": EDSM auto-lookups are turned off; no request was made
interface NearestScoopableStarResult {
  status: "ok" | "none_found" | "unavailable" | "disabled";
  system: string | null;
  distance: number | null;
  star_class: string | null;
}

interface GetStatusResult {
  ed_running: boolean;
  enabled: boolean;
  watcher_running: boolean;
  journal_path: string | null;
  journal_path_source: string | null;
  targets: TargetStatsMap;
  last_upload_time: string | null;
  last_upload_event: string | null;
  uploader_id: string;
  edsm_commander_name: string;
  edsm_api_key_set: boolean;
  edsm_lookups_enabled: boolean;
  edsm_notifications_enabled: boolean;
  edsm_notify_all_verdicts: boolean;
  detailed_logging: boolean;
  edsm_worth_scanning: EdsmWorthScanningVerdict | null;
  edsm_next_hop: EdsmNextHopPreview | null;
}

interface GetEdsmCredentialsResult {
  commander_name: string;
  api_key_set: boolean;
}

type SetEdsmCredentialsResult = BasicSuccessResult;

interface DiagnosticsResult {
  success: boolean;
  path?: string;
  size?: number;
  error?: string;
}

interface EdStateChangeEvent {
  ed_running: boolean;
}

interface SessionStats {
  commander: string;
  star_system: string;
  jumps: number;
  distance_ly: number;
  bodies_scanned: number;
  first_discoveries: number;
}

type SessionUpdateEvent = SessionStats;
