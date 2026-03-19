import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "..", "..");
const desktopRoot = path.resolve(import.meta.dirname, "..");
const version = fs.readFileSync(path.join(repoRoot, "VERSION"), "utf8").trim();

function updateJsonFile(filePath, transform) {
  const current = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const next = transform(current);
  fs.writeFileSync(filePath, `${JSON.stringify(next, null, 2)}\n`, "utf8");
}

function updateCargoVersion(filePath, nextVersion) {
  const current = fs.readFileSync(filePath, "utf8");
  const next = current.replace(/^version = ".*"$/m, `version = "${nextVersion}"`);
  fs.writeFileSync(filePath, next, "utf8");
}

updateJsonFile(path.join(desktopRoot, "package.json"), (pkg) => ({
  ...pkg,
  version,
}));

updateJsonFile(path.join(desktopRoot, "src-tauri", "tauri.conf.json"), (config) => ({
  ...config,
  version,
}));

updateCargoVersion(path.join(desktopRoot, "src-tauri", "Cargo.toml"), version);

console.log(`Synced desktop version to ${version}`);
