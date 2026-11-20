import { useApp } from "../app/store";
import { post } from "./api";
import { RECORD_MODE } from "./format";

let resetting = false;

/** Reset all demo state (simulation, onboarding, votes, sabotage, dial). Shared by the R key and the Reset button. */
export async function resetDemo() {
  if (resetting) return;
  resetting = true;
  try {
    await post("/demo/reset");
    useApp.getState().bumpEpoch();
    if (!RECORD_MODE) useApp.getState().showToast("Demo state reset"); // silent on camera
  } catch {
    useApp.getState().showToast("Reset failed. Check the backend and try again.", "clay");
  } finally {
    resetting = false;
  }
}
