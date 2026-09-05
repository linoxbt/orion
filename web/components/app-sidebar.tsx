"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  LayoutDashboard,
  PhoneCall,
  BookOpen,
  CreditCard,
  UserRound,
  PanelLeftClose,
  PanelLeft,
  X,
} from "lucide-react";
import { Wordmark } from "./wordmark";
import { LogoMark } from "./logo-mark";
import { useSidebar } from "./sidebar-context";
import { docsHref, siteHref } from "@/lib/site-urls";
import { UserChip } from "./auth/user-chip";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/negotiate", label: "New negotiation", icon: PhoneCall },
  { href: docsHref("/"), label: "Docs", icon: BookOpen },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/account", label: "Account", icon: UserRound },
];

function NavLinks({ collapsed, onNavigate, ariaLabel }: { collapsed: boolean; onNavigate?: () => void; ariaLabel: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label={ariaLabel} className="flex flex-col gap-1">
      {NAV.map((item) => {
        const active = pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={`flex items-center gap-3 rounded px-3 py-2.5 text-[13px] transition-colors ${
              active
                ? "bg-accent-soft font-medium text-accent"
                : "text-ink-soft hover:bg-surface-2 hover:text-ink"
            } ${collapsed ? "justify-center" : ""}`}
          >
            <Icon size={16} className="flex-none" />
            {!collapsed && <span>{item.label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppSidebar() {
  const { isCollapsed, toggleCollapsed } = useSidebar();

  return (
    <>
      {/* Desktop: collapsible rail/panel, participates in the flex layout. */}
      <aside
        className={`hidden flex-none flex-col border-r border-line bg-surface px-4 py-6 transition-all duration-200 md:flex ${
          isCollapsed ? "w-20 items-center" : "w-64"
        }`}
      >
        <div className={`mb-8 flex items-center ${isCollapsed ? "justify-center" : "justify-between"} px-2`}>
          <Link href={siteHref("/")}>{isCollapsed ? <LogoMark className="h-6 w-6 text-accent" /> : <Wordmark className="text-base" />}</Link>
        </div>

        {!isCollapsed && (
          <p className="mb-3 px-3 font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
            Menu
          </p>
        )}
        <NavLinks collapsed={isCollapsed} ariaLabel="Primary" />

        <div className={`mt-auto flex flex-col gap-3 pt-8 ${isCollapsed ? "items-center" : ""}`}>
          <UserChip collapsed={isCollapsed} />
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-line text-ink-soft transition-colors hover:border-accent hover:text-accent"
          >
            {isCollapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
          </button>
          {!isCollapsed && (
            <div className="flex flex-col gap-1">
              <Link href={siteHref("/")} className="text-[12px] text-muted transition-colors hover:text-ink">
                ← Back to site
              </Link>
            </div>
          )}
        </div>
      </aside>

      <MobileDrawer />
    </>
  );
}

function MobileDrawer() {
  const { isMobileOpen, closeMobile } = useSidebar();
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!isMobileOpen) return;
    const drawer = drawerRef.current;
    const focusables = drawer?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])');
    focusables?.[0]?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        closeMobile();
        return;
      }
      if (e.key !== "Tab" || !focusables || focusables.length === 0) return;
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isMobileOpen, closeMobile]);

  return (
    <>
      {/* Off-canvas drawer + backdrop, toggled from the dashboard layout's top bar. */}
      <div
        onClick={closeMobile}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity md:hidden ${
          isMobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Mobile navigation"
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col overflow-y-auto border-r border-line bg-surface px-4 py-6 transition-transform duration-200 md:hidden ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-8 flex items-center justify-between px-2">
          <Link href={siteHref("/")}>
            <Wordmark className="text-base" />
          </Link>
          <button type="button" onClick={closeMobile} aria-label="Close menu" className="text-ink/75">
            <X size={18} />
          </button>
        </div>
        <p className="mb-3 px-3 font-mono text-[9px] uppercase tracking-[0.22em] text-muted">Menu</p>
        <NavLinks collapsed={false} onNavigate={closeMobile} ariaLabel="Mobile primary" />

        {/* Sign out lives here on a phone. It was only ever in the desktop
            rail, so on mobile there was no way out of the app at all. */}
        <div className="mt-auto flex flex-none flex-col gap-3 pt-8">
          <UserChip collapsed={false} />
          <Link href={siteHref("/")} className="font-mono text-xs text-muted hover:text-ink">
            ← Back to site
          </Link>
        </div>
      </aside>
    </>
  );
}
