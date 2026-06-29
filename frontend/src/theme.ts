import type { ThemeConfig } from "antd";

// L'Oréal-inspired palette: black + gold on a light surface.
export const BRAND = {
  gold: "#B6862C",      // primary gold
  goldSoft: "#C9A85C",
  black: "#0A0A0A",
  ink: "#1A1A1A",
  surface: "#F5F3EF",   // warm light background
  paper: "#FFFFFF",
  border: "#E6E0D6",
};

export const lorealTheme: ThemeConfig = {
  token: {
    colorPrimary: BRAND.gold,
    colorLink: BRAND.gold,
    colorInfo: BRAND.gold,
    colorTextHeading: BRAND.ink,
    colorBgLayout: BRAND.surface,
    borderRadius: 8,
    fontFamily:
      "'Helvetica Neue', Helvetica, Arial, 'Segoe UI', Roboto, sans-serif",
    fontSize: 14,
  },
  components: {
    Layout: {
      headerBg: BRAND.black,
      headerColor: "#FFFFFF",
      headerHeight: 60,
      bodyBg: BRAND.surface,
    },
    Menu: { darkItemBg: BRAND.black, darkItemSelectedBg: BRAND.gold },
    Table: {
      headerBg: BRAND.ink,
      headerColor: "#FFFFFF",
      headerSortActiveBg: "#2a2a2a",
      rowHoverBg: "#FBF7EF",
    },
    Tabs: { inkBarColor: BRAND.gold, itemSelectedColor: BRAND.gold },
    Statistic: { contentFontSize: 26 },
    Card: { headerFontSize: 15 },
    Button: { primaryShadow: "none" },
  },
};

export const ERROR_RED = "#C0392B";

// shared color ramp for charts (gold-forward, black anchor)
export const CHART_COLORS = [
  BRAND.gold, BRAND.ink, BRAND.goldSoft, "#7A6A45", "#3D3D3D", "#D8C9A3",
];
