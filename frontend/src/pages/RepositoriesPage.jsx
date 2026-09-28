import { useState } from "react";
import ArchitectureCatalogDrawer from "../components/ArchitectureCatalogDrawer";
import RepoOnboarderCard from "../components/RepoOnboarderCard";

export default function RepositoriesPage({
  repositories,
  loading,
  error,
  onOnboarded,
  onDeleted,
}) {
  const [selectedRepo, setSelectedRepo] = useState(null);
  const readyCount = repositories.filter((repo) => repo.catalog_status === "ready").length;
  const analyzingCount = repositories.filter(
    (repo) => repo.catalog_status === "onboarding"
  ).length;

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
          <p className="page-kicker">Step 1 · Ground truth</p>
          <h1>Repositories</h1>
          <p className="page-sub">
            Connect a codebase once. Gemini maps architecture into a catalog that
            every meeting idea has to ground against — so attempts stay buildable.
          </p>
        </div>
      </header>

      <div className="page-steps" aria-label="How repositories feed the pipeline">
        <article className="page-step">
          <span className="page-step-index">01</span>
          <strong>Connect</strong>
          <p>GitHub OAuth or the Acme Store demo sandbox.</p>
        </article>
        <article className="page-step">
          <span className="page-step-index">02</span>
          <strong>Catalog</strong>
          <p>Modules, routes, models, and owners — analyzed in the background.</p>
        </article>
        <article className="page-step">
          <span className="page-step-index">03</span>
          <strong>Ground ideas</strong>
          <p>
            {readyCount > 0
              ? `${readyCount} catalog${readyCount === 1 ? "" : "s"} ready for meetings.`
              : analyzingCount > 0
                ? "Analysis running — ideas will use the catalog next."
                : "Ideas only surface when they map onto this catalog."}
          </p>
        </article>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading && repositories.length === 0 ? (
        <p className="detail-note">Loading repositories…</p>
      ) : null}

      <RepoOnboarderCard
        repositories={repositories}
        onOnboarded={onOnboarded}
        onDeleted={onDeleted}
        onViewCatalog={handleViewCatalog}
      />

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
