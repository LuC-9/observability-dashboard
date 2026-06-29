interface Props {
  tabs: string[];
  active: string;
  onChange: (t: string) => void;
}

export default function Tabs({ tabs, active, onChange }: Props) {
  return (
    <div className="tab-nav">
      {tabs.map((t) => (
        <button
          key={t}
          className={t === active ? "selected" : ""}
          onClick={() => onChange(t)}
        >
          {t}
        </button>
      ))}
    </div>
  );
}
