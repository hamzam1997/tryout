import { useEffect, useState } from "react";
import ArchitectureCatalogDrawer from "../components/ArchitectureCatalogDrawer";
import RepoOnboarderCard from "../components/RepoOnboarderCard";
import { getRepositoryCatalog } from "../api";

export default function RepositoriesPage({
  repositories,
  loading,
  error,
  onOnboarded,
  onDeleted,
  isEvaluator,
  onCatalogOpenChange,
}) {
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [loadingCatalogId, setLoadingCatalogId] = useState(null);
  const [catalogError, setCatalogError] = useState("");
  const readyCount = repositories.filter((repo) => repo.catalog_status === "ready").length;
  const analyzingCount = repositories.filter(
    (repo) => repo.catalog_status === "onboarding"
  ).length;

  // Lets the evaluator guide know the catalog drawer is open.
  const drawerOpen = Boolean(selectedRepo);
  useEffect(() => {
    onCatalogOpenChange?.(drawerOpen);
    return () => onCatalogOpenChange?.(false);
  }, [drawerOpen, onCatalogOpenChange]);

  async function handleViewCatalog(repo) {
    setLoadingCatalogId(repo.id);
    setCatalogError("");
    try {
      const fullCatalog = await getRepositoryCatalog(repo.id);
      setSelectedRepo({ ...repo, catalog: fullCatalog });
    } catch (err) {
      setCatalogError(`Failed to load catalog: ${err.message}`);
    } finally {
      setLoadingCatalogId(null);
    }
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
      {catalogError && <div className="alert alert-error">{catalogError}</div>}

      {loading && repositories.length === 0 ? (
        <p className="detail-note">Loading repositories…</p>
      ) : null}

      <RepoOnboarderCard
        repositories={repositories}
        onOnboarded={onOnboarded}
        onDeleted={onDeleted}
        onViewCatalog={handleViewCatalog}
        loadingCatalogId={loadingCatalogId}
        isEvaluator={isEvaluator}
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
