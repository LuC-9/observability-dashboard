import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";

dayjs.extend(utc);
dayjs.extend(timezone);

export const TZ_OPTIONS = [
  { value: "local", label: "Local (browser)" },
  { value: "utc", label: "UTC" },
  { value: "Asia/Singapore", label: "Asia/Singapore" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata" },
  { value: "Europe/Paris", label: "Europe/Paris" },
  { value: "America/New_York", label: "America/New_York" },
];

let zone = localStorage.getItem("tz") || "local";
export const getZone = () => zone;
export const setZone = (z: string) => { zone = z; localStorage.setItem("tz", z); };

export function fmtTime(v: any, f = "MMM D HH:mm:ss") {
  if (!v) return "—";
  const d = dayjs(v);
  if (zone === "local") return d.format(f);
  if (zone === "utc") return d.utc().format(f) + " UTC";
  try { return d.tz(zone).format(f); } catch { return d.format(f); }
}
