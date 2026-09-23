import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { workspacesApi } from "../api/client";
import { signOut } from "../api/signOut";
import { useCurrentWorkspaceId } from "../api/useCurrentWorkspaceId";
import { SchemaTree } from "../components/SchemaTree";
import { WorkspaceSwitcher } from "../components/WorkspaceSwitcher";

type SectionKey = "assets" | "tickets" | "documents";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "assets", label: "Assets" },
  { key: "tickets", label: "Tickets" },
  { key: "documents", label: "Documentation" },
];

const SECTION_CONFIG: Record<
  SectionKey,
  {
    links: { to: string; label: string }[];
    /** Where switching to this section takes you. Changing the sidebar
     * without changing the page leaves somebody looking at a document
     * while the menu says Tickets. */
    landing: string;
    treeLabel: string;
    newTypeTo: string;
    newTypeTitle: string;
    appliesTo: "objects" | "tickets" | "documents";
  }
> = {
  assets: {
    landing: "/assets/search",
    links: [
      { to: "/assets/search", label: "Search" },
      { to: "/labels", label: "Labels" },
      { to: "/global-values", label: "Global Values" },
    ],
    treeLabel: "Object types",
    newTypeTo: "/schemas/new",
    newTypeTitle: "New object type",
    appliesTo: "objects",
  },
  tickets: {
    landing: "/tickets",
    links: [
      { to: "/tickets", label: "All tickets" },
      { to: "/tickets/board", label: "Board" },
      { to: "/tickets/search", label: "Search" },
    ],
    treeLabel: "Ticket types",
    newTypeTo: "/schemas/new?applies_to=tickets",
    newTypeTitle: "New ticket type",
    appliesTo: "tickets",
  },
  documents: {
    landing: "/documents",
    links: [
      { to: "/documents", label: "All documents" },
      { to: "/documents/search", label: "Search" },
      { to: "/documents/suggestions", label: "Type suggestions" },
    ],
    treeLabel: "Document types",
    newTypeTo: "/schemas/new?applies_to=documents",
    newTypeTitle: "New document type",
    appliesTo: "documents",
  },
};

const SECTION_KEY = "assetmanagement.activeSection";
const DRAWER_KEY = "assetmanagement.sidebarDrawerOpen";

function readSection(): SectionKey {
  try {
    const v = localStorage.getItem(SECTION_KEY);
    if (v === "assets" || v === "tickets" || v === "documents") return v;
  } catch {
    // ignore
  }
  return "assets";
}

function readDrawerOpen(): boolean {
  try {
    return localStorage.getItem(DRAWER_KEY) === "1";
  } catch {
    return false;
  }
}

function SectionLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `block rounded px-3 py-1.5 text-sm ${
          isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

function SettingsLinks({ links }: { links: { to: string; label: string }[] }) {
  if (links.length === 0) return null;
  return (
    <div className="mt-1 border-t border-slate-100 pt-1">
      <p className="px-3 pt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        Settings
      </p>
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          className={({ isActive }) =>
            `block rounded px-3 py-1 text-xs ${
              isActive ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-100"
            }`
          }
        >
          {l.label}
        </NavLink>
      ))}
    </div>
  );
}

export function AppShell() {
  const me = useQuery({ queryKey: ["me"], queryFn: workspacesApi.me });
  const navigate = useNavigate();

  const currentWorkspaceId = useCurrentWorkspaceId();
  const membersLink = currentWorkspaceId ? `/workspaces/${currentWorkspaceId}/members` : null;
  const adminLink = membersLink ?? (me.data?.is_admin ? "/admin/workspaces" : null);

  const [activeSection, setActiveSection] = useState<SectionKey>(readSection);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(readDrawerOpen);

  useEffect(() => {
    try {
      localStorage.setItem(SECTION_KEY, activeSection);
    } catch {
      // ignore
    }
  }, [activeSection]);
  useEffect(() => {
    try {
      localStorage.setItem(DRAWER_KEY, drawerOpen ? "1" : "0");
    } catch {
      // ignore
    }
  }, [drawerOpen]);

  const config = SECTION_CONFIG[activeSection];
  const scopedMembersLink = membersLink ? `${membersLink}?section=${activeSection}` : null;
  const accessLink = currentWorkspaceId ? `/workspaces/${currentWorkspaceId}/access` : null;
  // Importing is not here: it configures a server and a credential for the
  // whole workspace, so it lives once in Administration rather than three
  // times, once per section that receives the content.
  const settingsLinks = [
    ...(accessLink ? [{ to: accessLink, label: "Access" }] : []),
    ...(scopedMembersLink ? [{ to: scopedMembersLink, label: "Members" }] : []),
  ];

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `block border-b border-slate-200 px-4 py-2.5 text-sm font-semibold ${
              isActive ? "bg-slate-50 text-slate-900" : "text-slate-900 hover:bg-slate-50"
            }`
          }
          title="Dashboard"
        >
          ARGUS Asset Knowledge Hub
        </NavLink>
        <WorkspaceSwitcher />

        <div className="border-t border-slate-200 px-2 py-1.5">
          {/* The graph crosses all three sections, so it sits above the
              section switcher rather than inside one of them. */}
          <SectionLink to="/graph">Knowledge graph</SectionLink>
          <SectionLink to="/ask">Ask</SectionLink>
        </div>

        <div className="flex flex-1 flex-col overflow-hidden border-t border-slate-200">
          {/* Collapsible drawer: section switcher + submenu + settings.
              Collapsed by default so the type tree below gets the space —
              you typically work in one of Assets/Tickets/Documentation at
              a time, not all three at once. */}
          <button
            type="button"
            onClick={() => setDrawerOpen((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <span>{SECTIONS.find((s) => s.key === activeSection)!.label}</span>
            <span className="text-xs text-slate-400">{drawerOpen ? "▾" : "▸"}</span>
          </button>

          {drawerOpen && (
            <div className="border-b border-slate-100 px-2 pb-2">
              <div className="flex gap-1 rounded bg-slate-100 p-1">
                {SECTIONS.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => {
                      setActiveSection(s.key);
                      navigate(SECTION_CONFIG[s.key].landing);
                    }}
                    className={`flex-1 rounded px-2 py-1 text-xs font-medium ${
                      activeSection === s.key
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              <div className="mt-2 space-y-0.5">
                {config.links.map((l) => (
                  <SectionLink key={l.to} to={l.to}>
                    {l.label}
                  </SectionLink>
                ))}
              </div>
              <SettingsLinks links={settingsLinks} />
            </div>
          )}

          {/* Type tree — always visible, gets all remaining vertical space. */}
          <div className="mt-1 flex min-h-0 flex-1 flex-col overflow-hidden px-2 pb-2">
            <div className="flex items-center justify-between px-1.5 pb-1 pt-1">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                {config.treeLabel}
              </p>
              <Link
                to={config.newTypeTo}
                title={config.newTypeTitle}
                className="rounded px-1.5 text-sm font-medium text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                +
              </Link>
            </div>
            <SchemaTree appliesTo={config.appliesTo} />
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 px-2 py-1.5 text-xs">
          {adminLink ? (
            <NavLink
              to={adminLink}
              className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            >
              Administration
            </NavLink>
          ) : (
            <span />
          )}
          <button
            onClick={() => void signOut()}
            className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
