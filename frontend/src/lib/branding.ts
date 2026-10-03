// Run-time branding (ADR-0003 section 2): a business's colours become CSS variables
// on :root, so every Tailwind class built on the tokens (bg-brand-primary...) follows
// them. One build serves every business; a rebrand needs no rebuild.
const HEX = /^#[0-9a-fA-F]{6}$/;
const WCAG_AA_NORMAL_TEXT = 4.5;

// The --text token (#1B1F1D) as RGB, for text on light brand colours.
const NEAR_BLACK_RGB: [number, number, number] = [27, 31, 29];
const WHITE_RGB: [number, number, number] = [255, 255, 255];

function rgbOf(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16)) as [number, number, number];
}

function luminance([r, g, b]: [number, number, number]): number {
  const channel = (value: number) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

/**
 * Text colour on the primary colour: white when it passes WCAG AA (the console refuses
 * primaries that don't, as the backend's colours.py does), otherwise whichever of white
 * and near-black reads better.
 */
export function onPrimaryFor(primary: string): "white" | "dark" {
  const rgb = rgbOf(primary);
  const white = contrastRatio(rgb, WHITE_RGB);
  if (white >= WCAG_AA_NORMAL_TEXT) return "white";
  return contrastRatio(rgb, NEAR_BLACK_RGB) > white ? "dark" : "white";
}

export interface Branding {
  primary_color: string;
  accent_color: string;
}

/** Set the brand variables; an invalid colour keeps the default token. */
export function applyBranding(branding: Branding, root: HTMLElement = document.documentElement) {
  const { style } = root;
  if (HEX.test(branding.primary_color)) {
    style.setProperty("--brand-primary", branding.primary_color);
    if (onPrimaryFor(branding.primary_color) === "dark") {
      style.setProperty("--brand-on-primary", "var(--text)");
    } else {
      style.removeProperty("--brand-on-primary"); // the token default, white
    }
  } else {
    style.removeProperty("--brand-primary");
    style.removeProperty("--brand-on-primary");
  }
  if (HEX.test(branding.accent_color)) style.setProperty("--brand-accent", branding.accent_color);
  else style.removeProperty("--brand-accent");
}
