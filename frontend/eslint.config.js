// ESLint (ADR-0003). Besides TypeScript and React hook rules, it enforces three
// project rules from CLAUDE.md section 6.8 and ADR-0003:
// - no user-facing text written straight into JSX: it goes through t();
// - no raw colour values: components use the design tokens;
// - no number formatting with toFixed/toLocaleString in screens: use src/lib/format.ts.
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules", "src/api/schema.d.ts"] },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXText[value=/[A-Za-z]/]",
          message: "User-facing text goes through t() with a screen-ID key (CLAUDE.md 6.8).",
        },
        {
          selector: "Literal[value=/^#[0-9a-fA-F]{3,8}$/]",
          message: "Use the design tokens (bg-brand-primary, text-danger...), not raw colours.",
        },
      ],
    },
  },
  {
    files: ["src/apps/**/*.{ts,tsx}", "src/components/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-properties": [
        "error",
        { property: "toFixed", message: "Format numbers with src/lib/format.ts." },
        { property: "toLocaleString", message: "Format with src/lib/format.ts." },
      ],
    },
  },
  {
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "no-restricted-syntax": "off" },
  },
);
