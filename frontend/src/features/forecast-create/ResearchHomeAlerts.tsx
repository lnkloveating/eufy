import { AlertTriangle } from "lucide-react";

export function ResearchHomeAlerts({
  backendOnline,
  llmConfigured,
}: {
  backendOnline: boolean;
  llmConfigured: boolean;
}) {
  return (
    <>
      {!backendOnline && (
        <div className="alert alert-danger" role="alert">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">后端未连接</span>
            <span>请先启动后端服务（默认 http://localhost:8000），再开始研究。</span>
          </div>
        </div>
      )}

      {backendOnline && !llmConfigured && (
        <div className="alert alert-warn" role="alert">
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">LLM 未配置</span>
            <span>
              后端未检测到 LLM API Key。多 Agent 研究依赖 LLM，请在后端环境变量中配置后再开始。前端不会保存或读取任何
              API Key。
            </span>
          </div>
        </div>
      )}
    </>
  );
}
