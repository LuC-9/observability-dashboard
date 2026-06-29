import type { StatusMsg } from "../types";

export default function StatusBanner({ msg }: { msg: StatusMsg }) {
  if (!msg.kind) return null;
  const cls = msg.kind === "ok" ? "status-ok" : msg.kind === "warn" ? "status-warn" : "status-error";
  // Errors stay; ok/warn fade out after 3s — restart animation when key changes.
  const fade = msg.kind !== "error" ? "status-fade" : "";
  return (
    <div className={`${cls} ${fade}`} key={msg.key} style={{ marginBottom: 12 }}>
      {msg.text}
    </div>
  );
}
