/** @type {import('eslint').Linter.Config} */
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/strict-type-checked",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: ["dist", ".eslintrc.cjs"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    project: ["./tsconfig.json", "./tsconfig.node.json"],
    tsconfigRootDir: __dirname,
  },
  plugins: ["@typescript-eslint"],
  rules: {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "error",
  },
};
