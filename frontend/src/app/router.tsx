import { createBrowserRouter, Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { AppShell } from "../components/AppShell/AppShell";
import { EmptyState } from "../components/EmptyState/EmptyState";
import { Button } from "../components/ui/Button";
import { DeepResearchHome } from "../features/forecast-create/DeepResearchHome";
import { RunWorkbenchPage } from "../features/forecast-run/RunWorkbenchPage";
import { ProductSpecPage } from "../features/product-spec/ProductSpecPage";
import { ProductDefinitionStatePage } from "../features/product-spec/ProductDefinitionStatePage";
import { ValidationLabPage } from "../features/validation/ValidationLabPage";

function NotFoundPage() {
  return (
    <div className="page">
      <EmptyState
        icon={<Compass size={26} aria-hidden="true" />}
        title="页面不存在"
        description="该地址没有对应的内容，可能任务或产品尚未创建。"
        action={
          <Link to="/">
            <Button variant="primary">返回研究首页</Button>
          </Link>
        }
      />
    </div>
  );
}

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <DeepResearchHome /> },
      { path: "runs/:runId", element: <RunWorkbenchPage /> },
      { path: "runs/:runId/product-definition", element: <ProductDefinitionStatePage /> },
      { path: "products/:productId", element: <ProductSpecPage /> },
      { path: "products/:productId/validation", element: <ValidationLabPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
