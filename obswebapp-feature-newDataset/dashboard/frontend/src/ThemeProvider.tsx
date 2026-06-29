import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { ConfigProvider, App as AntApp } from "antd";
import { lorealTheme } from "./theme";

// web-safe fonts (no external loading required)
const FONTS: Record<string, string> = {
  "System": "'Helvetica Neue', Helvetica, Arial, 'Segoe UI', Roboto, sans-serif",
  "Inter / Sans": "Inter, 'Segoe UI', Roboto, system-ui, sans-serif",
  "Georgia (serif)": "Georgia, 'Times New Roman', serif",
  "Verdana": "Verdana, Geneva, sans-serif",
  "Trebuchet": "'Trebuchet MS', Tahoma, sans-serif",
  "Courier (mono)": "'Courier New', Courier, monospace",
};
export const FONT_OPTIONS = Object.keys(FONTS);

const Ctx = createContext<{ font: string; setFont: (f: string) => void }>(null as any);
export const useThemeCtx = () => useContext(Ctx);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [font, setFontState] = useState<string>(localStorage.getItem("font") || "System");
  const setFont = (f: string) => { localStorage.setItem("font", f); setFontState(f); };
  const fontFamily = FONTS[font] || FONTS["System"];

  useEffect(() => { document.documentElement.style.fontFamily = fontFamily; }, [fontFamily]);

  const theme = { ...lorealTheme, token: { ...lorealTheme.token, fontFamily } };
  return (
    <Ctx.Provider value={{ font, setFont }}>
      <ConfigProvider theme={theme}>
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </Ctx.Provider>
  );
}
