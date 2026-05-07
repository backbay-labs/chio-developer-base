/**
 * tp.user.episode_id() — generate a slug for a new episode.
 *
 * Usage in episode template:
 *
 *     id: episode.<% await tp.user.episode_id(tp) %>
 *
 * Behavior:
 *   - Default: derive a kebab-case slug from the file title (alphanumerics + hyphens).
 *   - If the title is empty or starts with "untitled", fall back to a date-based
 *     slug (YYYY-MM-DD-untitled).
 *   - Strip frontmatter-unsafe characters; truncate to 60 chars.
 *
 * The slug is the part after `episode.` in frontmatter `id:` and the filename
 * (minus .md). Keep this script's slugify rules consistent with
 * ops/scripts/migrate-seeds.py (slugify) and the episode-promoter plugin
 * (vault/.obsidian/plugins/episode-promoter/src/main.ts) so new episodes
 * authored from any of the three paths produce identical slugs.
 */

module.exports = async (tp) => {
  const title = (tp.file.title || "").trim();
  const isUntitled = !title || title.toLowerCase().startsWith("untitled");

  if (isUntitled) {
    return tp.date.now("YYYY-MM-DD") + "-untitled";
  }

  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

  return slug || (tp.date.now("YYYY-MM-DD") + "-untitled");
};
