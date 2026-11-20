import { useEffect, useRef } from "react";
import { useApp, type WSMsg } from "../app/store";

let socket: WebSocket | null = null;

export function connectWS() {
  if (socket && socket.readyState <= 1) return;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${window.location.host}/ws`);
  socket.onopen = () => useApp.setState({ wsConnected: true });
  socket.onmessage = (ev) => {
    try {
      useApp.getState().dispatch(JSON.parse(ev.data) as WSMsg);
    } catch {
      /* ignore malformed */
    }
  };
  socket.onclose = () => {
    useApp.setState({ wsConnected: false });
    setTimeout(connectWS, 1000);
  };
}

/** Subscribe to a topic for the lifetime of a component. Handler may change between renders. */
export function useTopic(topic: string, handler: (m: WSMsg) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => useApp.getState().subscribe(topic, (m) => ref.current(m)), [topic]);
}
