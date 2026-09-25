import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useCurrentWorkspaceId } from "./api/useCurrentWorkspaceId";
import { TokenGate } from "./auth/TokenGate";
import { AdminShell } from "./layout/AdminShell";
import { AppShell } from "./layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { NewWorkspace } from "./pages/admin/NewWorkspace";
import { AdminSettings } from "./pages/admin/Settings";
import { AdminUsers } from "./pages/admin/Users";
import { AdminWorkspaces } from "./pages/admin/Workspaces";
import { AssetDetail } from "./pages/assets/Detail";
import { AssetForm } from "./pages/assets/Form";
import { AssetSearch } from "./pages/assets/Search";
import { DocumentDetail } from "./pages/documents/Detail";
import { DocumentForm } from "./pages/documents/Form";
import { DocumentList } from "./pages/documents/List";
import { DocumentSearch } from "./pages/documents/Search";
import { DocumentSuggestions } from "./pages/documents/Suggestions";
import { GlobalValueForm } from "./pages/globalvalues/Form";
import { Ask } from "./pages/ai/Ask";
import { GraphExplorer } from "./pages/graph/Explorer";
import { GlobalValueList } from "./pages/globalvalues/List";
import { ImportList } from "./pages/imports/List";
import { MarkdownImport } from "./pages/imports/Markdown";
import { ImportConfigForm } from "./pages/imports/New";
import { ImportStatus } from "./pages/imports/Status";
import { IssueBoard } from "./pages/issues/Board";
import { IssueDetail } from "./pages/issues/Detail";
import { IssueForm } from "./pages/issues/Form";
import { IssueList } from "./pages/issues/List";
import { IssueSearch } from "./pages/issues/Search";
import { LabelList } from "./pages/labels/List";
import { ReviewQueuePage } from "./pages/review/Queue";
import { MigrationPage } from "./pages/migration/Domains";
import { LookupPage } from "./pages/lookup/Lookup";
import { SchemaDetail } from "./pages/schemas/Detail";
import { IconLibrary } from "./pages/icons/List";
import { SchemaForm } from "./pages/schemas/Form";
import { WorkspaceAI } from "./pages/workspace/AI";
import { WorkspaceAccess } from "./pages/workspace/Access";
import { WorkspaceMembers } from "./pages/workspace/Members";
import { WorkspaceIntegrity } from "./pages/workspace/Integrity";
import { WorkspaceTransfer } from "./pages/workspace/Transfer";
import { TransferList } from "./pages/workspace/TransferList";
import { TransferStatus } from "./pages/workspace/TransferStatus";

/** Sends /imports/... to the workspace-scoped equivalent, keeping whatever
 * came after it. */
function LegacyImportRedirect() {
  const workspaceId = useCurrentWorkspaceId();
  const location = useLocation();
  if (!workspaceId) return null;
  const rest = location.pathname.replace(/^\/imports/, "");
  return (
    <Navigate
      to={`/workspaces/${workspaceId}/imports${rest}${location.search}`}
      replace
    />
  );
}

export function App() {
  return (
    <TokenGate>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Dashboard />} />

          <Route path="/ask" element={<Ask />} />

          <Route path="/schemas/new" element={<SchemaForm />} />
          <Route path="/schemas/:uid" element={<SchemaDetail />} />
          <Route path="/schemas/:uid/edit" element={<SchemaForm />} />

          <Route path="/assets/search" element={<AssetSearch />} />
          <Route path="/assets/new" element={<AssetForm />} />
          <Route path="/assets/:uid" element={<AssetDetail />} />
          <Route path="/assets/:uid/edit" element={<AssetForm />} />

          <Route path="/tickets" element={<IssueList />} />
          <Route path="/tickets/board" element={<IssueBoard />} />
          <Route path="/tickets/search" element={<IssueSearch />} />
          <Route path="/tickets/new" element={<IssueForm />} />
          <Route path="/tickets/:uid" element={<IssueDetail />} />
          <Route path="/tickets/:uid/edit" element={<IssueForm />} />

          <Route path="/documents" element={<DocumentList />} />
          <Route path="/documents/search" element={<DocumentSearch />} />
          <Route path="/documents/suggestions" element={<DocumentSuggestions />} />
          <Route path="/documents/new" element={<DocumentForm />} />
          <Route path="/documents/:uid" element={<DocumentDetail />} />

          <Route path="/graph" element={<GraphExplorer />} />
          <Route path="/review" element={<ReviewQueuePage />} />
          <Route path="/migration" element={<MigrationPage />} />
          <Route path="/lookup/*" element={<LookupPage />} />

          <Route path="/labels" element={<LabelList />} />

          <Route path="/global-values" element={<GlobalValueList />} />
          <Route path="/global-values/new" element={<GlobalValueForm />} />
          <Route path="/global-values/:uid/edit" element={<GlobalValueForm />} />

          {/* Imports moved under the workspace's settings; old links and
              bookmarks still land in the right place. */}
          <Route path="/imports/*" element={<LegacyImportRedirect />} />
        </Route>

        <Route element={<AdminShell />}>
          <Route path="/workspaces/:workspaceId/imports" element={<ImportList />} />
          <Route path="/workspaces/:workspaceId/imports/new" element={<ImportConfigForm />} />
          <Route path="/workspaces/:workspaceId/imports/markdown" element={<MarkdownImport />} />
          <Route
            path="/workspaces/:workspaceId/imports/configs/:uid/edit"
            element={<ImportConfigForm />}
          />
          <Route path="/workspaces/:workspaceId/imports/:uid" element={<ImportStatus />} />
          <Route path="/workspaces/:workspaceId/ai" element={<WorkspaceAI />} />
          <Route path="/workspaces/:workspaceId/access" element={<WorkspaceAccess />} />
          <Route path="/workspaces/:workspaceId/members" element={<WorkspaceMembers />} />
          <Route path="/workspaces/:workspaceId/integrity" element={<WorkspaceIntegrity />} />
          <Route path="/workspaces/:workspaceId/icons" element={<IconLibrary />} />
          <Route path="/workspaces/:workspaceId/transfer" element={<WorkspaceTransfer />} />
          <Route path="/workspaces/:workspaceId/transfers" element={<TransferList />} />
          <Route path="/workspaces/:workspaceId/transfers/:uid" element={<TransferStatus />} />
          <Route path="/admin/workspaces" element={<AdminWorkspaces />} />
          <Route path="/admin/new-workspace" element={<NewWorkspace />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/settings" element={<AdminSettings />} />
        </Route>
      </Routes>
    </TokenGate>
  );
}
