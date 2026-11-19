import layoutsJson from "@shared/layouts/layouts.json";
import editorialIndigo from "@shared/themes/editorial-indigo.json";
import warmAmber from "@shared/themes/warm-amber.json";
import monoGraphite from "@shared/themes/mono-graphite.json";
import freshTeal from "@shared/themes/fresh-teal.json";

export interface Slot {
  key: string;
  x: number;
  y: number;
  w: number;
  h: number;
  roles: string[];
}

export interface LayoutSpec {
  name: string;
  description: string;
  slots: Slot[];
}

export interface TextStyle {
  size: number;
  weight: number;
  colorRole: string;
  lineHeight: number;
}

export interface Theme {
  styleKey: string;
  name: string;
  version: number;
  scope: string;
  description: string;
  useCase: string;
  licenseStatus: string;
  palette: Record<string, string>;
  fonts: { display: string; body: string };
  textStyles: Record<string, TextStyle>;
  tokens: Record<string, string | number | boolean>;
}

const layouts = layoutsJson as {
  version: string;
  canvas: { width: number; height: number };
  chrome: Record<string, { x: number; y: number; w: number; h: number }>;
  layouts: Record<string, LayoutSpec>;
};

const THEMES: Record<string, Theme> = {
  "editorial-indigo": editorialIndigo as Theme,
  "warm-amber": warmAmber as Theme,
  "mono-graphite": monoGraphite as Theme,
  "fresh-teal": freshTeal as Theme,
};

export const CANVAS = layouts.canvas;
export const CHROME = layouts.chrome;
export const LAYOUTS = layouts.layouts;

export function getLayout(layoutId: string): LayoutSpec {
  return LAYOUTS[layoutId] ?? LAYOUTS.single;
}

export function getTheme(styleKey: string | undefined): Theme {
  return THEMES[styleKey ?? ""] ?? THEMES["editorial-indigo"];
}

export function allThemes(): Theme[] {
  return Object.values(THEMES);
}
