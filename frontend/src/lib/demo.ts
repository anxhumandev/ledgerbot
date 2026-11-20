import { useApp } from "../app/store";
import { post } from "./api";

let resetting = false;

/** Reset all demo state (simulation, onboarding, votes, sabotage, dial). Shared by the R key and the Reset button. */
export async function resetDemo() {
  if (resetting) return;
  resetting = true;
  try {
    await post("/demo/reset");
    useApp.getState().bumpEpoch();
    useApp.getState().showToast("Demo state reset");
  } catch {
    useApp.getState().showToast("Reset failed. Check the backend and try again.", "clay");
  } finally {
    resetting = false;
  }
}
