/** Importing is workspace configuration — a server URL, a credential and a
 * merge strategy — so it lives under the workspace's settings rather than
 * being reachable from each section that happens to receive the content. */
export const importPaths = {
  list: (workspaceId: string) => `/workspaces/${workspaceId}/imports`,
  create: (workspaceId: string, source?: string) =>
    `/workspaces/${workspaceId}/imports/new${source ? `?source=${source}` : ""}`,
  editConfig: (workspaceId: string, uid: string) =>
    `/workspaces/${workspaceId}/imports/configs/${uid}/edit`,
  job: (workspaceId: string, uid: string) => `/workspaces/${workspaceId}/imports/${uid}`,
  markdown: (workspaceId: string) => `/workspaces/${workspaceId}/imports/markdown`,
};

/** What each importer brings in, so every source is visible in one place —
 * Confluence had no entry point at all while the page was reached only
 * from the Assets and Tickets sections. */
export const IMPORT_SOURCES = [
  {
    source: "jira",
    label: "Jira objects",
    blurb: "Schemas and objects from a Jira Insight schema.",
  },
  {
    source: "jira-issues",
    label: "Jira tickets",
    blurb: "Issues from a Jira project, mapped onto ARGUS tickets and linked to the objects they name.",
  },
  {
    source: "confluence",
    label: "Confluence",
    blurb: "Pages and blogposts from a space, converted to Markdown with their attachments.",
  },
  {
    source: "git",
    label: "Git",
    // Deliberately narrow: the Git importer reads schemas/ and assets/ from
    // a repository. It does not read Markdown — uploading documentation is
    // what the Markdown importer is for.
    blurb: "Object types and objects defined as files in a repository.",
  },
  {
    source: "markdown",
    label: "Markdown files",
    blurb: "Upload .md files, or a zip of a folder, and the images they refer to come with them.",
    upload: true,
  },
] as const;
