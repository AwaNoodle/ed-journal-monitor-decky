import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.strict,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        project: "./tsconfig.json",
      },
    },
    rules: {
      // Enforce explicit return types on functions
      "@typescript-eslint/explicit-function-return-type": "error",
      // No any
      "@typescript-eslint/no-explicit-any": "error",
      // Consistent type imports
      "@typescript-eslint/consistent-type-imports": "error",
    },
  },
  {
    // Ignore dist and node_modules
    ignores: ["dist/**", "node_modules/**", ".opencode/**"],
  },
);
