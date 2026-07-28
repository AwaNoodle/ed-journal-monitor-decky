import { addEventListener, definePlugin, removeEventListener, toaster } from "@decky/api";
import { Navigation, QuickAccessTab, staticClasses } from "@decky/ui";
import { FaSatelliteDish } from "react-icons/fa";
import Content from "./Content";
import {
  checkEdRunning,
  findJournalPath,
  getStatus,
  setEdRunning,
  startWatcher,
  stopWatcher,
} from "./api";

const formatCredits = (value: number): string => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
};

// Subtext carrying value + top priority bodies, or undefined when the payload
// carries neutral value fields (rendering nothing rather than placeholder text).
const worthScanningSubtext = (data: EdsmWorthScanningEvent): string | undefined => {
  if (data.totalValue === null) return undefined;
  const bodies = data.priorityBodies.map((b): string => `${b.name} (${formatCredits(b.value)})`).join(", ");
  const value = `~${formatCredits(data.totalValue)} cr`;
  return bodies ? `${value} · ${bodies}` : value;
};

// Elite Dangerous Steam AppID
const ED_APP_ID = 359320;

export default definePlugin(() => {
  console.log("ED Journal Monitor initializing...");

  // Handle ED game start
  const handleAppStart = async (data: { unAppID: number; bRunning: boolean; nInstanceID?: number }): Promise<void> => {
    // Log all app lifecycle events for debugging
    console.log(`AppLifetimeNotification: appID=${String(data.unAppID)}, running=${String(data.bRunning)}, instanceID=${String(data.nInstanceID)}`);

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
      // If ED is still running and watcher should be active, log resume state.
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
    // SteamClient is declared as always-defined by @decky/ui but may be
    // unavailable at runtime on some SteamOS versions.
    const gameSessions = (SteamClient as unknown as Record<string, unknown>).GameSessions as
      typeof SteamClient.GameSessions | undefined;
    if (gameSessions) {
      console.log("Registering for AppLifetimeNotifications...");
      lifetimeRegistration = gameSessions.RegisterForAppLifetimeNotifications(
        (data): void => { void handleAppStart(data); },
      );
      console.log("AppLifetimeNotifications registered successfully");
    } else {
      console.warn("SteamClient.GameSessions not available, game lifecycle detection disabled");
    }
  } catch (e) {
    console.warn("Failed to register SteamClient.GameSessions listener", e);
  }

  try {
    const system = (SteamClient as unknown as Record<string, unknown>).System as
      typeof SteamClient.System | undefined;
    if (system) {
      console.log("Registering for OnResumeFromSuspend...");
      resumeRegistration = system.RegisterForOnResumeFromSuspend((): void => { void handleResume(); });
      console.log("OnResumeFromSuspend registered successfully");
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

  // Worth-scanning toast: registered here (not in Content.tsx) so it stays
  // alive for the whole Steam session, not just while the panel is open. The
  // backend decides notify — this listener only renders. Never fires from a
  // status rehydration, only from the live emitted event.
  const worthScanningListener = addEventListener("edsm_worth_scanning", (data: EdsmWorthScanningEvent): void => {
    if (!data.notify) return;
    toaster.toast({
      title: "Worth scanning",
      body: data.system,
      subtext: worthScanningSubtext(data),
      onClick: (): void => { Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky); },
    });
  });

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
      removeEventListener("edsm_worth_scanning", worthScanningListener);
    },
  };
});
