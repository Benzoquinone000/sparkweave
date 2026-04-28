import { Outlet, useLocation } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Suspense } from "react";

import { AppShell } from "@/components/layout/AppShell";

export function RootLayout() {
  const location = useLocation();

  return (
    <AppShell>
      <Suspense fallback={<LoadingState />}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            className="h-full"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </Suspense>
    </AppShell>
  );
}

function LoadingState() {
  return (
    <div className="flex h-full min-h-0 items-center justify-center bg-canvas px-6 text-center">
      <div className="rounded-lg border border-line bg-white px-5 py-4">
        <p className="text-sm font-semibold text-ink">正在准备学习工作台</p>
        <p className="mt-2 text-xs text-slate-500">加载当前页面与运行状态...</p>
      </div>
    </div>
  );
}
