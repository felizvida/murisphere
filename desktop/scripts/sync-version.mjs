/*
 * Copyright 2026 Murisphere Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

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
