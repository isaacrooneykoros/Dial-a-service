// Which app a page belongs to. One codebase serves three apps plus the console
// (00-design-doc.md, "Frontend"): the staff app, the rider app and the customer app
// (with the public order pages), and the business console. Each checks its own
// minimum version (X-02) and has its own log-in page. The platform admin is Django
// admin on its own host and is not part of this build.
export const APPS = ["staff", "console", "rider", "customer"] as const;
export type AppId = (typeof APPS)[number];

/** The web build; later Android builds (Capacitor) report "android". */
export const PLATFORM = "web";

export function appForPath(pathname: string): AppId {
  const first = pathname.split("/")[1] ?? "";
  return first === "staff" || first === "console" || first === "rider" ? first : "customer";
}

export function homePathFor(app: AppId): string {
  return app === "customer" ? "/" : `/${app}`;
}

export function loginPathForApp(app: AppId): string {
  return app === "customer" ? "/login" : `/${app}/login`;
}
