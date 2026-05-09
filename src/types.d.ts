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

// Decky API event listener types
interface StatusUpdateEvent {
  success_count: number;
  fail_count: number;
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

interface ActivityEntry {
  timestamp: string;
  event_type: string;
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
  success_count: number;
  fail_count: number;
  last_upload_time: string | null;
  last_upload_event: string | null;
  uploader_id: string;
  detailed_logging: boolean;
}

interface DiagnosticsResult {
  success: boolean;
  path?: string;
  size?: number;
  error?: string;
}

interface EdStateChangeEvent {
  ed_running: boolean;
}
