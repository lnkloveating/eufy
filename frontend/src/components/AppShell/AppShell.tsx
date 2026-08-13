import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import clsx from "clsx";
import {
  Activity,
  ChevronsRightLeft,
  FlaskConical,
  ScrollText,
  Sparkles,
} from "lucide-react";
import { useHealth } from "../../lib/queries";
import { getRecentProduct, getRecentRun } from "../../lib/recent";

/** Application frame with a collapsible navigation rail. */
export function AppShell() {
  const location = useLocation();
  void location.pathname;

  const health = useHealth();
  const recentRun = getRecentRun();
  const recentProduct = getRecentProduct();
  const [navCollapsed, setNavCollapsed] = useState(false);

  const backendOnline = health.isSuccess && !health.isError;
  const llmConfigured = health.data?.llm_configured ?? false;

  useEffect(() => {
    const saved = window.localStorage.getItem("eufy-nav-collapsed");
    if (saved === "true") {
      setNavCollapsed(true);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("eufy-nav-collapsed", String(navCollapsed));
  }, [navCollapsed]);

  return (
    <div className={clsx("shell", navCollapsed && "shell-nav-collapsed")}>
      <nav className="nav" aria-label="Primary navigation">
        <div className="nav-brand">
          <div className="nav-brand-main">
            <div className="nav-brand-text">
              <span className="nav-brand-name">Eufy 产品研究台</span>
            </div>
          </div>

          <button
            type="button"
            className={clsx("nav-collapse-btn", navCollapsed && "is-collapsed")}
            aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"}
            aria-pressed={navCollapsed}
            title={navCollapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={() => setNavCollapsed((value) => !value)}
          >
            <ChevronsRightLeft size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="nav-links-wrap stack stack-2">
          <span className="nav-section-label">工作流</span>

          <NavLink
            to="/"
            end
            title="研究首页"
            className={({ isActive }) => clsx("nav-link", isActive && "is-active")}
          >
            <Sparkles size={18} aria-hidden="true" />
            <span className="nav-link-label">研究首页</span>
          </NavLink>

          {recentRun ? (
            <NavLink
              to={`/runs/${recentRun}`}
              title="实时研究"
              className={({ isActive }) =>
                clsx("nav-link", isActive && location.pathname.startsWith("/runs") && "is-active")
              }
            >
              <Activity size={18} aria-hidden="true" />
              <span className="nav-link-label">实时研究</span>
            </NavLink>
          ) : (
            <span className="nav-link is-disabled" aria-disabled="true" title="实时研究">
              <Activity size={18} aria-hidden="true" />
              <span className="nav-link-label">实时研究</span>
            </span>
          )}

          {recentProduct ? (
            <NavLink
              to={`/products/${recentProduct}`}
              title="产品定义"
              className={({ isActive }) =>
                clsx(
                  "nav-link",
                  isActive && location.pathname.startsWith("/products") && "is-active",
                )
              }
            >
              <ScrollText size={18} aria-hidden="true" />
              <span className="nav-link-label">产品定义</span>
            </NavLink>
          ) : (
            <span className="nav-link is-disabled" aria-disabled="true" title="产品定义">
              <ScrollText size={18} aria-hidden="true" />
              <span className="nav-link-label">产品定义</span>
            </span>
          )}

          <span className="nav-section-label">下一步</span>
          <span
            className="nav-link is-disabled"
            aria-disabled="true"
            title="即将支持技术、商业、隐私和 2D 场景模拟验证"
          >
            <FlaskConical size={18} aria-hidden="true" />
            <span className="nav-link-label">验证实验室</span>
          </span>
        </div>

        <div className="nav-foot">
          <div className="nav-status-list">
            <div className="nav-health">
              <span
                className={clsx(
                  "dot",
                  backendOnline ? "dot-ok" : health.isLoading ? "dot-warn" : "dot-off",
                )}
              />
              <span className="nav-foot-label">
                {health.isLoading
                  ? "Connecting backend..."
                  : backendOnline
                    ? "Backend online"
                    : "Backend offline"}
              </span>
            </div>

            {backendOnline && (
              <div className="nav-health">
                <span className={clsx("dot", llmConfigured ? "dot-ok" : "dot-warn")} />
                <span className="nav-foot-label">
                  {llmConfigured ? "LLM configured" : "LLM missing"}
                </span>
              </div>
            )}
          </div>

          {backendOnline && (
            <div className="nav-meta">
              <span className="mono nav-model-name">{health.data?.llm_model}</span>
            </div>
          )}
        </div>
      </nav>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
