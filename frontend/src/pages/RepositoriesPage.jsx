import { useState } from "react";
import ArchitectureCatalogDrawer from "../components/ArchitectureCatalogDrawer";
import RepoOnboarderCard from "../components/RepoOnboarderCard";

export default function RepositoriesPage({
  repositories,
  loading,
  error,
  onRefresh,
  onOnboarded,
  onDeleted,
}) {
  const [selectedRepo, setSelectedRepo] = useState(null);

  function handleViewCatalog(repo) {
    setSelectedRepo(repo);
  }

  function handleCloseDrawer() {
    setSelectedRepo(null);
  }

  return (
    <div className="container">
      <header className="page-head">
        <div>
          <h1>Repositories</h1>
          <p className="page-sub">
            Onboard a codebase once. Gemini builds an architecture catalog that
            grounds every meeting idea.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      <RepoOnboarderCard
        repositories={repositories}
        onOnboarded={onOnboarded}
        onDeleted={onDeleted}
        onViewCatalog={handleViewCatalog}
      />

      {/* Slide-out Architecture Catalog Drawer */}
      {selectedRepo && (
        <ArchitectureCatalogDrawer
          repository={selectedRepo}
          catalog={selectedRepo.catalog}
          onClose={handleCloseDrawer}
        />
      )}
    </div>
  );
}
