/*
 * Episode Promoter — promote a daily note's "What I learned" section to a
 * Graphiti episode candidate.
 *
 * Architectural rule (from AGENTS.md):
 *   - This plugin writes vault/episodes/<slug>.md ONLY. It does NOT call
 *     Graphiti directly. The vault-sync daemon (Phase 1) is the only writer
 *     to Graphiti and will derive the episode from the new file's frontmatter.
 *
 * UX (from PLAN.md Moonshot #1 / Obsidian-UX brainstorm):
 *   - "Promote to episode" command in command palette.
 *   - Available only when the active file lives under vault/daily/.
 *   - Parses the "## What I learned" section.
 *   - Opens a modal showing proposed title / slug / type / body. ALL editable.
 *   - On Confirm: writes vault/episodes/<slug>.md.
 *   - On Cancel or empty section: no-op. Auto-promotion would poison the graph.
 */

import {
  App,
  MarkdownView,
  Modal,
  Notice,
  Plugin,
  Setting,
  TFile,
} from "obsidian";

interface EpisodePromoterSettings {
  episodesFolder: string;
  whatILearnedHeading: string;
}

const DEFAULT_SETTINGS: EpisodePromoterSettings = {
  episodesFolder: "episodes",
  whatILearnedHeading: "## What I learned",
};

interface DraftEpisode {
  slug: string;
  title: string;
  type: string;
  summary: string;
  authoritativeFiles: string[];
  sourceDailyNote: string;
}

const EPISODE_TYPES: Record<string, string> = {
  "episode-architecture-summary":  "architecture summary",
  "episode-architecture-decision": "architecture decision",
  "episode-release-note":          "release note",
  "episode-pr-repair":             "PR repair summary",
  "episode-session-note":          "session note",
};

export default class EpisodePromoter extends Plugin {
  settings!: EpisodePromoterSettings;

  async onload() {
    await this.loadSettings();

    this.addCommand({
      id: "promote-to-episode",
      name: "Promote 'What I learned' to episode",
      checkCallback: (checking: boolean) => {
        const view = this.app.workspace.getActiveViewOfType(MarkdownView);
        if (!view || !this.isDailyNote(view.file)) return false;
        if (!checking) this.runPromotion(view);
        return true;
      },
    });
  }

  private isDailyNote(file: TFile | null): boolean {
    return !!file && file.path.startsWith("daily/");
  }

  private async runPromotion(view: MarkdownView) {
    const text = view.editor.getValue();
    const section = this.extractSection(text, this.settings.whatILearnedHeading);
    if (!section || section.trim().length === 0) {
      new Notice("Episode promoter: 'What I learned' section is empty");
      return;
    }

    const draft = this.draftEpisode(section, view.file?.path ?? "");
    new ConfirmModal(this.app, draft, async (confirmed) => {
      if (!confirmed) {
        new Notice("Episode promotion cancelled");
        return;
      }
      try {
        const path = await this.writeEpisode(draft);
        new Notice(`Wrote ${path}. The vault-sync daemon will derive the Graphiti episode.`);
      } catch (e) {
        new Notice(`Episode promoter error: ${(e as Error).message}`);
      }
    }).open();
  }

  private extractSection(text: string, heading: string): string {
    const lines = text.split("\n");
    const start = lines.findIndex((l) => l.trim() === heading);
    if (start === -1) return "";
    const after = lines.slice(start + 1);
    const next = after.findIndex((l) => /^#{1,6}\s/.test(l));
    const body = next === -1 ? after : after.slice(0, next);
    return body.join("\n").trim();
  }

  private draftEpisode(body: string, sourcePath: string): DraftEpisode {
    const firstSentence = body.split(/[.!?]\s/)[0].trim();
    const titleGuess =
      firstSentence.length > 70
        ? firstSentence.slice(0, 70) + "…"
        : firstSentence;
    return {
      slug: this.slugify(titleGuess),
      title: titleGuess,
      type: "episode-architecture-summary",
      summary: body,
      authoritativeFiles: [],
      sourceDailyNote: sourcePath,
    };
  }

  private slugify(s: string): string {
    return s
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "untitled";
  }

  private async writeEpisode(draft: DraftEpisode): Promise<string> {
    const path = `${this.settings.episodesFolder}/${draft.slug}.md`;
    if (this.app.vault.getAbstractFileByPath(path)) {
      throw new Error(`${path} already exists. Choose a different slug.`);
    }
    const fm = [
      "---",
      `id: episode.${draft.slug}`,
      `type: ${draft.type}`,
      "status: draft",
      "scope: chio-repo",
      `title: ${JSON.stringify(draft.title)}`,
      `graphiti_episode_name: ${JSON.stringify(draft.title)}`,
      `source_description: ${JSON.stringify("Promoted from " + draft.sourceDailyNote)}`,
      "authoritative_files: []",
      `imported_at: ${new Date().toISOString()}`,
      "---",
      "",
      `# ${draft.title}`,
      "",
      draft.summary,
      "",
      "<!-- HUMAN EDITS BELOW THIS LINE -->",
      "",
    ].join("\n");

    await this.app.vault.create(path, fm);
    return path;
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }
}

class ConfirmModal extends Modal {
  draft: DraftEpisode;
  onResult: (confirmed: boolean) => void;

  constructor(app: App, draft: DraftEpisode, onResult: (confirmed: boolean) => void) {
    super(app);
    this.draft = draft;
    this.onResult = onResult;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.createEl("h2", { text: "Promote to episode" });
    contentEl.createEl("p", {
      text: "The vault-sync daemon will derive a Graphiti episode from the file you create here. Edit anything before confirming.",
      cls: "setting-item-description",
    });

    new Setting(contentEl).setName("Title").addText((t) =>
      t.setValue(this.draft.title).onChange((v) => {
        this.draft.title = v;
      })
    );

    new Setting(contentEl).setName("Slug").addText((t) =>
      t.setValue(this.draft.slug).onChange((v) => {
        this.draft.slug = v;
      })
    );

    new Setting(contentEl).setName("Type").addDropdown((d) => {
      Object.entries(EPISODE_TYPES).forEach(([k, v]) => d.addOption(k, v));
      d.setValue(this.draft.type).onChange((v) => {
        this.draft.type = v;
      });
    });

    contentEl.createEl("h3", { text: "Body preview" });
    const ta = contentEl.createEl("textarea", {
      attr: { rows: "10", style: "width: 100%; font-family: var(--font-monospace);" },
    });
    ta.value = this.draft.summary;
    ta.addEventListener("input", () => {
      this.draft.summary = ta.value;
    });

    new Setting(contentEl)
      .addButton((b) =>
        b.setButtonText("Cancel").onClick(() => {
          this.close();
          this.onResult(false);
        })
      )
      .addButton((b) =>
        b.setButtonText("Confirm").setCta().onClick(() => {
          this.close();
          this.onResult(true);
        })
      );
  }

  onClose() {
    this.contentEl.empty();
  }
}
