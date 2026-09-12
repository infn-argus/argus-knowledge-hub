import { Route, Routes } from "react-router-dom";
import { TokenGate } from "./auth/TokenGate";
import { AdminShell } from "./layout/AdminShell";
import { AppShell } from "./layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { NewWorkspace } from "./pages/admin/NewWorkspace";
import { AdminUsers } from "./pages/admin/Users";
import { AdminWorkspaces } from "./pages/admin/Workspaces";
import { AssetDetail } from "./pages/assets/Detail";
import { AssetForm } from "./pages/assets/Form";
import { AssetSearch } from "./pages/assets/Search";
import { DocumentDetail } from "./pages/documents/Detail";
import { DocumentForm } from "./pages/documents/Form";
import { DocumentList } from "./pages/documents/List";
import { DocumentSearch } from "./pages/documents/Search";
import { GlobalValueForm } from "./pages/globalvalues/Form";
import { GlobalValueList } from "./pages/globalvalues/List";
import { ImportList } from "./pages/imports/List";
import { ImportConfigForm } from "./pages/imports/New";
import { ImportStatus } from "./pages/imports/Status";
import { IssueDetail } from "./pages/issues/Detail";
import { IssueForm } from "./pages/issues/Form";
import { IssueList } from "./pages/issues/List";
import { IssueSearch } from "./pages/issues/Search";
import { LabelList } from "./pages/labels/List";
import { SchemaDetail } from "./pages/schemas/Detail";
import { SchemaForm } from "./pages/schemas/Form";
import { WorkspaceMembers } from "./pages/workspace/Members";
import { WorkspaceIntegrity } from "./pages/workspace/Integrity";

export function App() {
  return (
    <TokenGate>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Dashboard />} />

          <Route path="/schemas/new" element={<SchemaForm />} />
          <Route path="/schemas/:uid" element={<SchemaDetail />} />
          <Route path="/schemas/:uid/edit" element={<SchemaForm />} />

          <Route path="/assets/search" element={<AssetSearch />} />
          <Route path="/assets/new" element={<AssetForm />} />
          <Route path="/assets/:uid" element={<AssetDetail />} />
          <Route path="/assets/:uid/edit" element={<AssetForm />} />

          <Route path="/tickets" element={<IssueList />} />
          <Route path="/tickets/search" element={<IssueSearch />} />
          <Route path="/tickets/new" element={<IssueForm />} />
          <Route path="/tickets/:uid" element={<IssueDetail />} />

          <Route path="/documents" element={<DocumentList />} />
          <Route path="/documents/search" element={<DocumentSearch />} />
          <Route path="/documents/new" element={<DocumentForm />} />
          <Route path="/documents/:uid" element={<DocumentDetail />} />

          <Route path="/labels" element={<LabelList />} />

          <Route path="/global-values" element={<GlobalValueList />} />
          <Route path="/global-values/new" element={<GlobalValueForm />} />
          <Route path="/global-values/:uid/edit" element={<GlobalValueForm />} />

          <Route path="/imports" element={<ImportList />} />
          <Route path="/imports/new" element={<ImportConfigForm />} />
          <Route path="/imports/configs/:uid/edit" element={<ImportConfigForm />} />
          <Route path="/imports/:uid" element={<ImportStatus />} />
        </Route>

        <Route element={<AdminShell />}>
          <Route path="/workspaces/:workspaceId/members" element={<WorkspaceMembers />} />
          <Route path="/workspaces/:workspaceId/integrity" element={<WorkspaceIntegrity />} />
          <Route path="/admin/workspaces" element={<AdminWorkspaces />} />
          <Route path="/admin/new-workspace" element={<NewWorkspace />} />
          <Route path="/admin/users" element={<AdminUsers />} />
        </Route>
      </Routes>
    </TokenGate>
  );
}
