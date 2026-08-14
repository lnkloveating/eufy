import type { RunProductDefinitionState } from "../types/api";

export interface ProductDefinitionNavigation {
  path: string;
  label: string;
  title: string;
}

export function getProductDefinitionNavigation(
  runId: string,
  state: RunProductDefinitionState | undefined,
): ProductDefinitionNavigation {
  const statusPath = `/runs/${encodeURIComponent(runId)}/product-definition`;

  if (!state || state.run_id !== runId) {
    return { path: statusPath, label: "产品定义", title: "正在检查产品定义状态" };
  }

  switch (state.status) {
    case "researching":
      return { path: statusPath, label: "产品定义 · 预测中", title: "研究与产品预测正在进行" };
    case "awaiting_selection":
      return { path: statusPath, label: "产品定义 · 待选择", title: "研究完成，等待选择候选产品" };
    case "generating":
      return { path: statusPath, label: "产品定义 · 生成中", title: "正在生成产品定义" };
    case "ready":
      return state.product_id
        ? {
            path: `/products/${encodeURIComponent(state.product_id)}`,
            label: "产品定义",
            title: "打开当前研究的产品定义",
          }
        : { path: statusPath, label: "产品定义", title: "产品定义状态异常" };
    case "failed":
      return { path: statusPath, label: "产品定义 · 未生成", title: "产品定义尚未生成" };
  }
}
