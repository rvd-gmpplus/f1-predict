"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";
import { Sidebar } from "./Sidebar";

const navLinks = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/predict", label: "Predict" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/ai-insights", label: "AI Insights" },
  { href: "/calendar", label: "Calendar" },
  { href: "/history", label: "My History" },
];

export function Navbar() {
  const pathname = usePathname();
  const { user, isAuthenticated, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 bg-f1-carbon/90 backdrop-blur-md border-b border-f1-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-f1-red rounded-lg flex items-center justify-center font-bold text-sm">
                F1
              </div>
              <span className="font-bold text-lg hidden sm:block">
                F1 <span className="text-f1-red">Predict</span>
              </span>
            </Link>

            {/* Desktop nav links */}
            {isAuthenticated && (
              <div className="hidden lg:flex items-center gap-1">
                {navLinks.map((link) => {
                  const isActive =
                    pathname === link.href || pathname.startsWith(link.href + "/");
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={cn(
                        "px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
                        isActive
                          ? "bg-f1-red/10 text-f1-red"
                          : "text-gray-400 hover:text-white hover:bg-white/5",
                      )}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </div>
            )}

            {/* Right side */}
            <div className="flex items-center gap-3">
              {isAuthenticated ? (
                <>
                  <div className="hidden sm:flex items-center gap-2 text-sm">
                    <div className="w-8 h-8 rounded-full bg-f1-surface-light flex items-center justify-center text-xs font-bold border border-f1-border">
                      {user?.username?.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-gray-300">{user?.username}</span>
                  </div>
                  <button onClick={logout} className="btn-ghost text-sm">
                    Sign Out
                  </button>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href="/auth/login" className="btn-ghost text-sm">
                    Sign In
                  </Link>
                  <Link href="/auth/register" className="btn-primary text-sm">
                    Sign Up
                  </Link>
                </div>
              )}

              {/* Mobile menu button */}
              {isAuthenticated && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="lg:hidden p-2 text-gray-400 hover:text-white"
                  aria-label="Open menu"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} links={navLinks} />
    </>
  );
}
