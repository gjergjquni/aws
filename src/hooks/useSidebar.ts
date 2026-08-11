import { useCallback, useState } from "react";
import { STORAGE_KEYS } from "@/lib/constants";

export function useSidebar() {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === "true";
    } catch {
      return false;
    }
  });

  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(STORAGE_KEYS.sidebarCollapsed, String(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  }, []);

  return {
    collapsed,
    mobileOpen,
    setMobileOpen,
    toggleCollapsed,
    sidebarWidth: collapsed ? 68 : 240,
  };
}
