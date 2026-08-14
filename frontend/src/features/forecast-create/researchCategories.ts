export const CATEGORY_OPTIONS = [
  "安防",
  "清洁",
  "护理",
  "母婴",
  "宠物",
  "健康生活",
  "智能照明",
  "安防摄像头",
  "室内摄像头",
  "室外摄像头",
  "视频门铃",
  "智能门锁",
  "HomeBase / 智能存储",
  "智能追踪器",
  "报警系统",
  "智能显示屏",
  "安防配件",
  "扫地机器人",
  "割草机器人",
  "清洁配件",
  "智能体重秤",
  "吸奶器",
  "婴儿监护器",
  "智能袜",
  "宠物摄像头",
] as const;

const SPLIT_PATTERN = /\s*\/\s*|\s*、\s*|\s*，\s*|\s*,\s*/;

export function parseCategorySelections(category: string | null | undefined): string[] {
  if (!category) return [];
  return [...new Set(category.split(SPLIT_PATTERN).map((item) => item.trim()).filter(Boolean))];
}

export function serializeCategorySelections(values: string[]): string {
  const unique = [...new Set(values.map((item) => item.trim()).filter(Boolean))];
  return unique.join(" / ");
}
