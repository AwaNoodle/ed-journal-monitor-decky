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
  detailed_logging: boolean;
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
