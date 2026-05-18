import { useCallback, useEffect, useState } from "react";

export function useGuideSectionHighlight() {
  const [highlightedSectionId, setHighlightedSectionId] = useState<string | null>(null);

  const scrollToGuideSection = useCallback((sectionId: string) => {
    setHighlightedSectionId(sectionId);
    window.setTimeout(() => {
      const element = document.getElementById(sectionId);
      if (!element) return;
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  }, []);

  useEffect(() => {
    if (!highlightedSectionId) return undefined;
    const timer = window.setTimeout(() => setHighlightedSectionId(null), 2200);
    return () => window.clearTimeout(timer);
  }, [highlightedSectionId]);

  return {
    highlightedSectionId,
    setHighlightedSectionId,
    scrollToGuideSection,
  };
}
