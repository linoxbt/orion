"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { Wordmark } from "@/components/wordmark";
import { SidebarProvider, useSidebar } from "@/components/sidebar-context";
import { AppSidebar } from "@/components/app-sidebar";
import { AuthGate } from "@/components/auth/auth-gate";

function MobileTopBar() {
  const { toggleMobileOpen } = useSidebar();
  return (
    <div className="flex items-center justify-between border-b border-line px-6 py-4 md:hidden">
      <Link href="/">
        <Wordmark className="text-base" />
      </Link>
      <button type="button" onClick={toggleMobileOpen} aria-label="Open menu" className="text-ink-soft">
        <Menu size={20} />
      </button>
    </div>
  );
}

/** Everything under (shell) is the signed-in application: uploading a bill,
 * authorising Orion, placing a call, and being charged for a win. All of it
 * sits behind AuthGate, and the proxy routes those pages call verify the same
 * session server-side. */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <SidebarProvider>
        <div className="flex min-h-screen">
          <AppSidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <MobileTopBar />
            <main className="min-w-0 flex-1 px-6 py-10 md:px-12 md:py-14">{children}</main>
          </div>
        </div>
      </SidebarProvider>
    </AuthGate>
  );
}
