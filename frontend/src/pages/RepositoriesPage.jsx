import { useState } from "react";
import ArchitectureCatalogDrawer from "../components/ArchitectureCatalogDrawer";
import RepoOnboarderCard from "../components/RepoOnboarderCard";

export default function RepositoriesPage({
  repositories,
  loading,
  error,
  onRefresh,
  onOnboarded,
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
          <h1>Codebase Repositories</h1>
          <p className="page-sub">
            Onboard repositories via GitHub OAuth or demo sandbox. Gemini synthesizes their architectural catalog.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onRefresh}
          disabled={loading}
        >
          Refresh
        </button>
      </header>

      {error && <div className="alert alert-error">{error}</div>}

      <RepoOnboarderCard
        repositories={repositories}
        onOnboarded={onOnboarded}
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
