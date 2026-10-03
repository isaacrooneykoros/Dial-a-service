import i18n, { resources } from "@/i18n";

type Tree = { [key: string]: string | Tree };

function keys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([key, value]) =>
    typeof value === "string" ? [`${prefix}${key}`] : keys(value, `${prefix}${key}.`),
  );
}

describe("i18n", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("falls back to English while Swahili is untranslated (D-23)", async () => {
    await i18n.changeLanguage("sw");
    expect(i18n.t("shared:areas.staff")).toBe("Staff app");
  });

  it("uses Swahili when a translation exists", async () => {
    i18n.addResource("sw", "shared", "areas.staff", "Programu ya wafanyakazi");
    await i18n.changeLanguage("sw");
    expect(i18n.t("shared:areas.staff")).toBe("Programu ya wafanyakazi");
    i18n.removeResourceBundle("sw", "shared");
    i18n.addResourceBundle("sw", "shared", {});
  });

  it("every Swahili key also exists in English", () => {
    const english = new Set(keys(resources.en.shared as Tree));
    const extra = keys(resources.sw.shared as Tree).filter((key) => !english.has(key));
    expect(extra).toEqual([]);
  });

  it("missing keys are visible in development, never blank", () => {
    expect(i18n.t("shared:no.such.key")).toBe("no.such.key");
  });
});
