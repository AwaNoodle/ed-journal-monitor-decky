import {
  definePlugin,
  callable,
} from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSatelliteDish } from "react-icons/fa";
import type { JSX } from "react";
import Content from "./Content";

// Backend callables
const startWatcher = callable<[], Record<string, unknown>>("start_watcher");
const stopWatcher = callable<[], Record<string, unknown>>("stop_watcher");
const findJournalPath = callable<[], FindPathResult>("find_journal_path");
const getStatus = callable<[], GetStatusResult>("get_status");

// Elite Dangerous Steam AppID
const ED_APP_ID = 359320;

export default definePlugin(() => {
  console.log("ED Journal Monitor initializing...");

  // Handle ED game start
  const handleAppStart = async (data: { unAppID: number; bRunning: boolean }): Promise<void> => {
    if (data.unAppID !== ED_APP_ID) return;

    if (data.bRunning) {
      console.log("Elite Dangerous started, starting watcher...");
      try {
        // Re-scan for journal path if needed
        const pathResult = await findJournalPath();
        if (pathResult.success) {
          await startWatcher();
        } else {
          console.warn("Journal path not found, watcher not started");
        }
      } catch (e) {
        console.error("Failed to start watcher on ED launch", e);
      }
    } else {
      console.log("Elite Dangerous stopped, stopping watcher...");
      try {
        await stopWatcher();
      } catch (e) {
        console.error("Failed to stop watcher on ED exit", e);
      }
    }
  };

  // Handle system resume from suspend
  const handleResume = async (): Promise<void> => {
    console.log("System resumed from suspend, re-checking watcher...");
    try {
      const status = await getStatus();
      if (status.watcher_running && !status.enabled) {
        // Watcher was running before suspend but is now disabled
        await stopWatcher();
      }
      // If ED is still running and watcher should be active, do a catch-up poll
      if (status.enabled && status.watcher_running) {
        console.log("Resuming watcher after suspend");
      }
    } catch (e) {
      console.error("Failed to handle resume", e);
    }
  };

  // Register SteamClient lifecycle listeners
  const lifetimeRegistration = SteamClient.GameSessions.RegisterForAppLifetimeNotifications(
    (data): void => { void handleAppStart(data); },
  );
  const resumeRegistration = SteamClient.System.RegisterForOnResumeFromSuspend((): void => { void handleResume(); });

  return {
    name: "ED Journal Monitor",
    titleView: <div className={staticClasses.Title}>ED Journal Monitor</div>,
    content: Content as unknown as JSX.Element,
    icon: <FaSatelliteDish />,
    onDismount(): void {
      console.log("ED Journal Monitor unloading");
      // Unregister all SteamClient listeners
      lifetimeRegistration.unregister();
      resumeRegistration.unregister();
    },
  };
});
