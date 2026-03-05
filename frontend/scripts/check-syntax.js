const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");

const jsFiles = fs
  .readdirSync(root, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
  .map((entry) => path.join(root, entry.name));

if (jsFiles.length === 0) {
  console.log("No JavaScript files found for syntax check.");
  process.exit(0);
}

jsFiles.forEach((file) => {
  execFileSync(process.execPath, ["--check", file], { stdio: "inherit" });
});

console.log(`Syntax OK for ${jsFiles.length} file(s).`);
