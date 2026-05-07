/*
 * Bump the plugin version across manifest.json and versions.json.
 *
 * Usage:
 *   npm version <patch|minor|major>
 *
 * Identical to episode-promoter/version-bump.mjs. The npm `version` lifecycle
 * runs this after package.json is updated; we mirror into the plugin's
 * Obsidian-facing manifest and the version → minAppVersion map.
 */
import { readFileSync, writeFileSync } from "node:fs";

const targetVersion = process.env.npm_package_version;
if (!targetVersion) {
  console.error("Run via `npm version <patch|minor|major>` so npm sets npm_package_version.");
  process.exit(1);
}

const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
const minAppVersion = manifest.minAppVersion;
manifest.version = targetVersion;
writeFileSync("manifest.json", JSON.stringify(manifest, null, 2) + "\n");

const versions = JSON.parse(readFileSync("versions.json", "utf8"));
versions[targetVersion] = minAppVersion;
writeFileSync("versions.json", JSON.stringify(versions, null, 2) + "\n");

console.log(`Bumped to ${targetVersion} (minAppVersion ${minAppVersion}).`);
