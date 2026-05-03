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
}

interface UploadSuccessEvent {
  total_success: number;
}

interface UploadFailedEvent {
  total_failed: number;
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
  enabled: boolean;
  watcher_running: boolean;
  journal_path: string | null;
  journal_path_source: string | null;
  success_count: number;
  fail_count: number;
  last_upload_time: string | null;
  uploader_id: string;
}
