import { AnimatePresence, motion } from "framer-motion";
import { Component, lazy, type ReactNode, Suspense, useEffect, useRef, useState } from "react";
import { Footer, PresenterOverlay, Rail, TopBar } from "../components/Chrome";
import { Skeleton, Stage, T, ToastHost } from "../design/primitives";
import { api, post } from "../lib/api";
import { RECORD_MODE } from "../lib/format";
import { typing } from "../lib/hooks";
import { connectWS } from "../lib/ws";
import { useApp } from "./store";

const scenes = [
  lazy(() => import("../scenes/S00ColdOpen")),
  lazy(() => import("../scenes/S01Mess")),
  lazy(() => import("../scenes/S02Onboarding")),
  lazy(() => import("../scenes/S03Inspector")),
  lazy(() => import("../scenes/S04BreakIt")),
  lazy(() => import("../scenes/S05Dial")),
  lazy(() => import("../scenes/S06Suppliers")),
  lazy(() => import("../scenes/S07Ranking")),
  lazy(() => import("../scenes/S08Arena")),
  lazy(() => import("../scenes/S09Impact")),
];
const VotePage = lazy(() => import("../scenes/VotePage"));

function useRecordMode() {
  useEffect(() => {
    if (!RECORD_MODE) return;
    document.body.classList.add("recording");
    let t: ReturnType<typeof setTimeout>;
    const idle = () => {
      document.body.classList.remove("record-mode");
      clearTimeout(t);
      t = setTimeout(() => document.body.classList.add("record-mode"), 2000);
    };
    idle();
    window.addEventListener("mousemove", idle);
    return () => {
      clearTimeout(t);
      window.removeEventListener("mousemove", idle);
      document.body.classList.remove("recording", "record-mode");
    };
  }, []);
}

class SceneBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };

  static getDerivedStateFromError() { return { error: true }; }

  render() {
    if (!this.state.error) return this.props.children;
    return <div role="alert" className="h-full flex flex-col items-center justify-center gap-4">
      <h1 className="font-serif text-[44px]">This scene could not load.</h1>
      <button className="rounded-full bg-lagoon text-white px-5 py-2" onClick={() => useApp.getState().bumpEpoch()}>Retry scene</button>
    </div>;
  }
}

function StageApp() {
  const resetting = useRef(false);
  const { scene, epoch, presenter, toast } = useApp();
  const [health, setHealth] = useState<any>(null);
  useRecordMode();
  useEffect(() => {
    connectWS();
    const poll = () => api("/health").then((h) => { setHealth(h); useApp.setState({ llm: h.llm }); }).catch(() => setHealth(null));
    poll();
    api("/cost").then((c) => useApp.setState({ cost: c })).catch(() => undefined);
    const id = setInterval(poll, 5000);
    const onHash = () => {
      const m = window.location.hash.match(/#(\d+)/);
      if (m && parseInt(m[1], 10) !== useApp.getState().scene) useApp.getState().setScene(parseInt(m[1], 10));
    };
    window.addEventListener("hashchange", onHash);
    return () => { clearInterval(id); window.removeEventListener("hashchange", onHash); };
  }, []);
  useEffect(() => {
    const on = async (e: KeyboardEvent) => {
      if (typing() || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowRight" && !e.shiftKey) useApp.getState().next();
      else if (e.key === "ArrowLeft" && !e.shiftKey) useApp.getState().prev();
      else if (e.key === "p" || e.key === "P") useApp.getState().togglePresenter();
      else if (e.key === "r" || e.key === "R") {
        if (e.repeat || resetting.current) return;
        resetting.current = true;
        try {
          await post("/demo/reset");
          useApp.getState().bumpEpoch();
          useApp.getState().showToast("Demo state reset");
        } catch {
          useApp.getState().showToast("Reset failed. Check the backend and press R to retry.", "clay");
        } finally {
          resetting.current = false;
        }
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
  const Scene = scenes[scene];
  return (
    <Stage>
      <TopBar />
      {presenter && <Rail />}
      <div className="absolute left-0 right-0 top-14 bottom-7 px-16 pt-10 pb-4 z-10">
        {!health?.ok ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 text-ink-2">
            <div className="font-serif text-[44px] text-ink">Warming up the pipeline…</div>
            <div className="text-[16px] max-w-[760px] text-center">{health?.error ?? "Waiting for the backend at /api (make dev)."}</div>
            <Skeleton className="w-[520px] h-3 mt-4" />
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div key={`${scene}-${epoch}`} className="h-full" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={T}>
              <Suspense fallback={<Skeleton className="w-full h-full" />}>
                <SceneBoundary><Scene /></SceneBoundary>
              </Suspense>
            </motion.div>
          </AnimatePresence>
        )}
      </div>
      <Footer />
      <PresenterOverlay />
      <ToastHost toast={toast} />
    </Stage>
  );
}

export default function App() {
  if (window.location.pathname.startsWith("/vote")) {
    return (
      <Suspense fallback={null}>
        <VotePage />
      </Suspense>
    );
  }
  return <StageApp />;
}
