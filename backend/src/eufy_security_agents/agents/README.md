# Agent boundaries

当前Agent均通过统一 `StructuredLLM` 接口生成Pydantic结构化对象：

- `FuturesLensAgent`：四个独立预测视角，并行执行。
- `LensDeliberationAgent`：四个视角交叉审核、质疑并修正自身观点。
- `ForecastConsensusAgent`：裁决共识、分歧、少数意见和证据缺口。
- `OpportunitySynthesizerAgent`：基于预测与审议只聚合机会，不生成产品。
- `ProductArchitectAgent`：生成差异化硬件产品，并支持确定性校验后的定向修复。
- `CandidateReviewerAgent`：五个评审维度，盲评时隐藏产品名。
- `ProductDefinitionAgent`：将用户选择的候选转成标准ProductSpec。

具体产品名称或方向不得写进系统Prompt。验证结果也不得由这些Agent提前生成。
