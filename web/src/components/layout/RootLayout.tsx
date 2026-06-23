import { Outlet, useLocation } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { Suspense } from "react";

import { AppShell } from "@/components/layout/AppShell";

export function RootLayout() {
  const location = useLocation();
  const page = (
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
  );

  if (location.pathname === "/") return page;
  return <AppShell>{page}</AppShell>;
}

function LoadingState() {
  return (
    <div className="h-full min-h-0 bg-canvas px-4 py-5">
      <div className="mx-auto flex h-full max-w-6xl flex-col gap-4">
        <div className="rounded-lg border border-line bg-white/90 px-4 py-3">
          <p className="text-sm font-semibold text-ink">正在准备工作台</p>
          <div className="mt-3 space-y-2">
            <span className="block h-2.5 w-48 max-w-full rounded bg-slate-100" />
            <span className="block h-2.5 w-32 rounded bg-slate-100" />
          </div>
        </div>
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.55fr)]">
          <div className="rounded-lg border border-line bg-white/80 p-4">
            <div className="h-4 w-40 rounded bg-slate-100" />
            <div className="mt-6 space-y-3">
              <div className="h-12 rounded-lg bg-slate-100/80" />
              <div className="h-12 rounded-lg bg-slate-100/70" />
              <div className="h-12 rounded-lg bg-slate-100/60" />
            </div>
          </div>
          <div className="hidden rounded-lg border border-line bg-white/75 p-4 lg:block">
            <div className="h-4 w-28 rounded bg-slate-100" />
            <div className="mt-6 space-y-3">
              <div className="h-16 rounded-lg bg-slate-100/70" />
              <div className="h-16 rounded-lg bg-slate-100/60" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
