import { appForPath, homePathFor, loginPathForApp } from "@/lib/apps";
import { applyBranding, contrastRatio, onPrimaryFor } from "@/lib/branding";
import { compareVersions, isBelowMinimum } from "@/lib/version";

describe("apps", () => {
  it.each([
    ["/staff/queue", "staff", "/staff", "/staff/login"],
    ["/console", "console", "/console", "/console/login"],
    ["/rider/jobs", "rider", "/rider", "/rider/login"],
    ["/", "customer", "/", "/login"],
    ["/o/abc", "customer", "/", "/login"],
    ["/staffroom", "customer", "/", "/login"],
  ])("%s belongs to the %s app", (path, app, home, login) => {
    const id = appForPath(path);
    expect(id).toBe(app);
    expect(homePathFor(id)).toBe(home);
    expect(loginPathForApp(id)).toBe(login);
  });
});

describe("versions", () => {
  it.each([
    ["1.2.3", "1.2.3", 0],
    ["1.10.0", "1.9.3", 1],
    ["1.2", "1.2.0", 0],
    ["0.9.9", "1.0.0", -1],
    ["2.0.0-beta.1", "2.0.0", 0],
  ])("%s vs %s", (a, b, sign) => {
    expect(Math.sign(compareVersions(a, b))).toBe(sign);
  });

  it("is below the minimum only when strictly older", () => {
    expect(isBelowMinimum("1.4.0", "1.4.0")).toBe(false);
    expect(isBelowMinimum("1.3.9", "1.4.0")).toBe(true);
    expect(isBelowMinimum("0.1.0", "0.0.0")).toBe(false);
  });
});

describe("branding", () => {
  afterEach(() => document.documentElement.removeAttribute("style"));

  it("matches the WCAG contrast of known pairs", () => {
    expect(contrastRatio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    // The default brand green against white, as the backend checks it.
    expect(contrastRatio([15, 107, 92], [255, 255, 255])).toBeGreaterThan(4.5);
  });

  it("uses white text on dark primaries and dark text on light ones", () => {
    expect(onPrimaryFor("#0F6B5C")).toBe("white");
    expect(onPrimaryFor("#F2A900")).toBe("dark");
  });

  it("sets the brand variables on :root", () => {
    applyBranding({ primary_color: "#7A1F5C", accent_color: "#F2A900" });
    const style = document.documentElement.style;
    expect(style.getPropertyValue("--brand-primary")).toBe("#7A1F5C");
    expect(style.getPropertyValue("--brand-accent")).toBe("#F2A900");
    expect(style.getPropertyValue("--brand-on-primary")).toBe("");
  });

  it("switches text on primary to near-black for a light primary", () => {
    applyBranding({ primary_color: "#F5F5A0", accent_color: "#F2A900" });
    expect(document.documentElement.style.getPropertyValue("--brand-on-primary")).toBe(
      "var(--text)",
    );
  });

  it("keeps the default tokens for anything that isn't a colour", () => {
    applyBranding({ primary_color: "#7A1F5C", accent_color: "#F2A900" });
    applyBranding({ primary_color: "red; background: url(x)", accent_color: "" });
    const style = document.documentElement.style;
    expect(style.getPropertyValue("--brand-primary")).toBe("");
    expect(style.getPropertyValue("--brand-accent")).toBe("");
  });
});
