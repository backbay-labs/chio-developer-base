/*
 * Bump the plugin version across manifest.json, package.json, and versions.json.
 *
 * Usage:
 *   npm version <patch|minor|major>
 *
 * The npm `version` script in package.json invokes this file after npm has
 * already updated package.json's `version` field. We mirror that into
 * manifest.json and append a row to versions.json (which Obsidian uses to
 * map plugin versions to minimum app versions).
 *
 * The npm `version` lifecycle then `git add`s the three files and creates
 * a git tag. Plugin tags are independent of repo tags.
 */
import { readFileSync, writeFileSync } from "node:fs";

const targetVersion = process.env.npm_package_version;
if (!targetVersion) {
  console.error("Run via `npm version <patch|minor|major>` so npm sets npm_package_version.");
  process.exit(1);
}

// 1. manifest.json — set the version + minimum app version
const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
const minAppVersion = manifest.minAppVersion;
manifest.version = targetVersion;
writeFileSync("manifest.json", JSON.stringify(manifest, null, 2) + "\n");

// 2. versions.json — append the new version → minAppVersion mapping
const versions = JSON.parse(readFileSync("versions.json", "utf8"));
versions[targetVersion] = minAppVersion;
writeFileSync("versions.json", JSON.stringify(versions, null, 2) + "\n");

console.log(`Bumped to ${targetVersion} (minAppVersion ${minAppVersion}).`);
