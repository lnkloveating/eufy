export interface SupplementalSourceDraft {
  id: string;
  kind: "url" | "file";
  name: string;
  url?: string;
  fileType?: string;
  fileSize?: number;
}

export interface SupplementalResearchSources {
  autoPublicResearch: false;
  enterpriseSources: SupplementalSourceDraft[];
  focusSources: SupplementalSourceDraft[];
}

export function createEmptySupplementalSources(): SupplementalResearchSources {
  return { autoPublicResearch: false, enterpriseSources: [], focusSources: [] };
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function fileToSourceDraft(file: File): SupplementalSourceDraft {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    kind: "file",
    name: file.name,
    fileType: file.type || "application/octet-stream",
    fileSize: file.size,
  };
}
