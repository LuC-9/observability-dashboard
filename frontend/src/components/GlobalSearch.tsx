import { useEffect, useRef, useState } from "react";
import { Modal, AutoComplete } from "antd";
import { get } from "../api";

export type SearchAction = { type: string; value: string };

export default function GlobalSearch({
  open, setOpen, onAction,
}: { open: boolean; setOpen: (b: boolean) => void; onAction: (a: SearchAction) => void }) {
  const [options, setOptions] = useState<any[]>([]);
  const [val, setVal] = useState("");
  const timer = useRef<any>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [setOpen]);

  const onSearch = (q: string) => {
    setVal(q);
    clearTimeout(timer.current);
    if (q.length < 2) { setOptions([]); return; }
    timer.current = setTimeout(() => {
      get("/search", { q }).then((d: any) => {
        const grp = (label: string, type: string, arr: string[]) =>
          arr && arr.length ? { label, options: arr.map((v) => ({ value: `${type}:${v}`, label: v })) } : null;
        setOptions([
          grp("Traces", "trace", d.traces),
          grp("Services", "service", d.services),
          grp("Projects", "project", d.projects),
          grp("Sessions", "session", d.conversations),
          grp("Models", "model", d.models),
        ].filter(Boolean) as any[]);
      });
    }, 300);
  };

  const onSelect = (value: string) => {
    const i = value.indexOf(":");
    onAction({ type: value.slice(0, i), value: value.slice(i + 1) });
    setOpen(false); setVal(""); setOptions([]);
  };

  return (
    <>
      <Modal open={open} onCancel={() => setOpen(false)} footer={null} title="Global search" destroyOnHidden>
        <AutoComplete autoFocus style={{ width: "100%" }} options={options} value={val}
          onSearch={onSearch} onSelect={onSelect}
          placeholder="Search trace id, service, project, session, model…" />
        <div style={{ marginTop: 8, color: "#999" }}>
          Pick a result: services/projects set the filter, traces open the span tree, sessions jump to Sessions.
        </div>
      </Modal>
    </>
  );
}
