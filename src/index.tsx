import {
  definePlugin,
  callable,
} from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSatelliteDish } from "react-icons/fa";
import Content from "./Content";

declare const SteamClient: {
  GameSessions: {
    RegisterForAppLifetimeNotifications(cb: (data: { unAppID: number; bRunning: boolean }) => void): { unregister(): void };
  } | undefined;
  System: {
    RegisterForOnResumeFromSuspend(cb: () => void): { unregister(): void };
  } | undefined;
} | undefined;

// Backend callables
const startWatcher = callable<[], Record<string, unknown>>("start_watcher");
const stopWatcher = callable<[], Record<string, unknown>>("stop_watcher");
const findJournalPath = callable<[], FindPathResult>("find_journal_path");
const getStatus = callable<[], GetStatusResult>("get_status");
const setEdRunning = callable<[boolean], Record<string, unknown>>("set_ed_running");
const checkEdRunning = callable<[], { running: boolean; reason?: string }>("check_ed_running");

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
        // Notify backend that ED is running
        try {
          await setEdRunning(true);
        } catch (e) {
          console.error("Failed to set ED running state", e);
        }
        // Check if monitor is enabled before starting
        const status = await getStatus();
        if (!status.enabled) {
          console.log("Monitor is disabled, not starting watcher");
          return;
        }
        // Re-scan for journal path if needed
        const pathResult = await findJournalPath();
        if (pathResult.success) {
          const result = await startWatcher();
          if (!result.success) {
            console.warn("Watcher failed to start:", result.error);
          }
        } else {
          console.warn("Journal path not found, watcher not started");
        }
      } catch (e) {
        console.error("Failed to start watcher on ED launch", e);
      }
    } else {
      console.log("Elite Dangerous stopped, stopping watcher...");
      try {
        // Notify backend that ED is not running
        try {
          await setEdRunning(false);
        } catch (e) {
          console.error("Failed to set ED running state", e);
        }
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

  // Register SteamClient lifecycle listeners (guard against SteamClient being unavailable)
  let lifetimeRegistration: { unregister(): void } | null = null;
  let resumeRegistration: { unregister(): void } | null = null;

  try {
    if (SteamClient?.GameSessions) {
      lifetimeRegistration = SteamClient.GameSessions.RegisterForAppLifetimeNotifications(
        (data): void => { void handleAppStart(data); },
      );
    } else {
      console.warn("SteamClient.GameSessions not available, game lifecycle detection disabled");
    }
  } catch (e) {
    console.warn("Failed to register SteamClient.GameSessions listener", e);
  }

  try {
    if (SteamClient?.System) {
      resumeRegistration = SteamClient.System.RegisterForOnResumeFromSuspend((): void => { void handleResume(); });
    } else {
      console.warn("SteamClient.System not available, suspend/resume handling disabled");
    }
  } catch (e) {
    console.warn("Failed to register SteamClient.System listener", e);
  }

  // Check if ED is already running on plugin load
  // (RegisterForAppLifetimeNotifications only fires on state changes)
  void (async (): Promise<void> => {
    try {
      const edCheck = await checkEdRunning();
      if (edCheck.running) {
        console.log("ED appears to already be running, triggering startup logic...");
        await handleAppStart({ unAppID: ED_APP_ID, bRunning: true });
      }
    } catch (e) {
      console.warn("Failed to check if ED is already running", e);
    }
  })();

  return {
    name: "ED Journal Monitor",
    titleView: <div className={staticClasses.Title}>ED Journal Monitor</div>,
    content: <Content />,
    icon: <FaSatelliteDish />,
    onDismount(): void {
      console.log("ED Journal Monitor unloading");
      // Unregister all SteamClient listeners
      lifetimeRegistration?.unregister();
      resumeRegistration?.unregister();
    },
  };
});
