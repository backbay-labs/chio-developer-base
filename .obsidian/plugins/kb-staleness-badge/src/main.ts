/*
 * KB Staleness Badge
 *
 * Shows a colored badge in the active note's title bar based on the
 * `last-validated:` frontmatter field. Helps make spec/playbook staleness
 * visible at a glance without opening the stale-specs dashboard.
 *
 * Thresholds match what stale-specs.md, the daily-note morning brief,
 * and the release-qualification playbook use:
 *
 *   <  30 days  →  green   (fresh)
 *   30..89      →  yellow  (gentle nudge)
 *   90..179     →  orange  (stale-specs query flags it)
 *   >= 180      →  red     (release blocker per release-qualification)
 *
 * Notes without `last-validated:` get no badge. Notes whose value doesn't
 * parse as YYYY-MM-DD also get no badge — the plugin is best-effort, not
 * a contract.
 */

import { MarkdownView, Plugin } from "obsidian";

interface StalenessSettings {
  yellowDays: number;
  orangeDays: number;
  redDays: number;
}

const DEFAULT_SETTINGS: StalenessSettings = {
  yellowDays: 30,
  orangeDays: 90,
  redDays: 180,
};

const COLORS = {
  green: "#2f855a",
  yellow: "#d99124",
  orange: "#dd6b20",
  red: "#d15451",
};

const BADGE_CLASS = "kb-staleness-badge";

export default class StalenessBadge extends Plugin {
  settings!: StalenessSettings;

  async onload() {
    await this.loadSettings();

    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => this.refresh())
    );

    this.registerEvent(
      this.app.metadataCache.on("changed", (file) => {
        const active = this.app.workspace.getActiveFile();
        if (active && active.path === file.path) this.refresh();
      })
    );

    this.app.workspace.onLayoutReady(() => this.refresh());
  }

  onunload() {
    this.removeBadges();
  }

  private refresh() {
    this.removeBadges();

    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (!view || !view.file) return;

    const cache = this.app.metadataCache.getFileCache(view.file);
    const lastValidated = cache?.frontmatter?.["last-validated"];
    if (!lastValidated) return;

    const date = parseDate(lastValidated);
    if (!date) return;

    const ageDays = Math.floor((Date.now() - date.getTime()) / 86_400_000);
    const color = this.colorFor(ageDays);
    this.renderBadge(view, ageDays, color);
  }

  private colorFor(ageDays: number): string {
    if (ageDays >= this.settings.redDays) return COLORS.red;
    if (ageDays >= this.settings.orangeDays) return COLORS.orange;
    if (ageDays >= this.settings.yellowDays) return COLORS.yellow;
    return COLORS.green;
  }

  private renderBadge(view: MarkdownView, ageDays: number, color: string) {
    const container = view.containerEl.querySelector(
      ".view-header-title-container"
    ) as HTMLElement | null;
    if (!container) return;

    const badge = document.createElement("span");
    badge.classList.add(BADGE_CLASS);
    badge.textContent = `${ageDays}d`;
    badge.title =
      `Validated ${ageDays} day${ageDays === 1 ? "" : "s"} ago. ` +
      `Yellow at ${this.settings.yellowDays}+, orange at ${this.settings.orangeDays}+, ` +
      `red at ${this.settings.redDays}+ (release blocker per release-qualification playbook).`;

    Object.assign(badge.style, {
      marginLeft: "8px",
      padding: "2px 6px",
      borderRadius: "3px",
      fontSize: "0.75em",
      fontWeight: "600",
      fontFamily: "var(--font-monospace)",
      color: "white",
      background: color,
      cursor: "help",
    });

    container.appendChild(badge);
  }

  private removeBadges() {
    document.querySelectorAll(`.${BADGE_CLASS}`).forEach((e) => e.remove());
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }
}

function parseDate(input: unknown): Date | null {
  if (!input) return null;
  if (input instanceof Date) return input;
  const s = String(input);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return isNaN(d.getTime()) ? null : d;
}
