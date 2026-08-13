import { NavLink, Outlet, useLocation } from "react-router-dom";
import clsx from "clsx";
import {
  Activity,
  FlaskConical,
  Radar,
  ScrollText,
  Sparkles,
} from "lucide-react";
import { useHealth } from "../../lib/queries";
import { getRecentProduct, getRecentRun } from "../../lib/recent";

/** Application frame: dark navigation rail + routed content area. */
export function AppShell() {
  const location = useLocation();
  // Re-read on every navigation so freshly created runs/products appear.
  void location.pathname;
  const health = useHealth();
  const recentRun = getRecentRun();
  const recentProduct = getRecentProduct();

  const backendOnline = health.isSuccess && !health.isError;
  const llmConfigured = health.data?.llm_configured ?? false;

  return (
    <div className="shell">
      <nav className="nav" aria-label="主导航">
        <div className="nav-brand">
          <div className="nav-logo" aria-hidden="true">
            <Radar size={22} />
          </div>
          <div className="nav-brand-text">
            <span className="nav-brand-name">eufy FutureLab</span>
            <span className="nav-brand-sub">AI Forecasting Workbench</span>
          </div>
        </div>

        <div className="nav-links-wrap stack stack-2">
          <span className="nav-section-label">工作流</span>
          <NavLink
            to="/"
            end
            className={({ isActive }) => clsx("nav-link", isActive && "is-active")}
          >
            <Sparkles size={18} aria-hidden="true" />
            研究首页
          </NavLink>

          <NavLink
            to={recentRun ? `/runs/${recentRun}` : "/"}
            className={({ isActive }) =>
              clsx(
                "nav-link",
                isActive && location.pathname.startsWith("/runs") && "is-active",
                !recentRun && "is-disabled",
              )
            }
            aria-disabled={!recentRun}
            onClick={(event) => {
              if (!recentRun) event.preventDefault();
            }}
          >
            <Activity size={18} aria-hidden="true" />
            Live Research
          </NavLink>

          <NavLink
            to={recentProduct ? `/products/${recentProduct}` : "/"}
            className={({ isActive }) =>
              clsx(
                "nav-link",
                isActive &&
                  location.pathname.startsWith("/products") &&
                  "is-active",
                !recentProduct && "is-disabled",
              )
            }
            aria-disabled={!recentProduct}
            onClick={(event) => {
              if (!recentProduct) event.preventDefault();
            }}
          >
            <ScrollText size={18} aria-hidden="true" />
            ProductSpec
          </NavLink>

          <span className="nav-section-label">下一阶段</span>
          <span
            className="nav-link is-disabled"
            aria-disabled="true"
            title="即将支持技术、商业、隐私和 2D 场景模拟"
          >
            <FlaskConical size={18} aria-hidden="true" />
            产品验证实验室
          </span>
        </div>

        <div className="nav-foot">
          <div className="nav-health">
            <span
              className={clsx(
                "dot",
                backendOnline ? "dot-ok" : health.isLoading ? "dot-warn" : "dot-off",
              )}
            />
            {health.isLoading
              ? "正在连接后端…"
              : backendOnline
                ? "后端在线"
                : "后端离线"}
          </div>
          {backendOnline && (
            <>
              <div className="nav-health">
                <span className={clsx("dot", llmConfigured ? "dot-ok" : "dot-warn")} />
                {llmConfigured ? "LLM 已配置" : "LLM 未配置"}
              </div>
              <span className="mono" style={{ color: "#6f83a0" }}>
                {health.data?.llm_model}
              </span>
            </>
          )}
        </div>
      </nav>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
