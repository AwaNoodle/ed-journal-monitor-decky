import { callable } from "@decky/api";

export const getStatus = callable<[], GetStatusResult>("get_status");
export const startWatcher = callable<[], StartWatcherResult>("start_watcher");
export const stopWatcher = callable<[], StopWatcherResult>("stop_watcher");
export const findJournalPath = callable<[], FindPathResult>("find_journal_path");
export const setManualJournalPath = callable<[string], SetManualPathResult>("set_journal_path");
export const setEnabled = callable<[boolean], SetEnabledResult>("set_enabled");
export const setUploaderId = callable<[string], SetUploaderIdResult>("set_uploader_id");
export const setDetailedLogging = callable<[boolean], SetDetailedLoggingResult>("set_detailed_logging");
export const setEdRunning = callable<[boolean], BasicSuccessResult>("set_ed_running");
export const checkEdRunning = callable<[], { running: boolean; reason?: string }>("check_ed_running");
export const createDiagnosticsBundle = callable<[], DiagnosticsResult>("create_diagnostics");
export const getRecentActivity = callable<[number?, string?], ActivityEntry[]>("get_recent_activity");
export const getSessionStats = callable<[], SessionStats>("get_session_stats");
