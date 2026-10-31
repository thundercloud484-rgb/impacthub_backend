"use client";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState, useRef, useEffect } from "react";
import { Search, Bell, PlusSquare, Home, Compass, CalendarCheck, LogOut, User, Settings, Trophy, X, Menu } from "lucide-react";
import { useAuthStore } from "@/store/auth.store";
import Avatar from "@/components/ui/Avatar";
import { cn } from "@/lib/utils";
import CreatePostModal from "@/components/post/CreatePostModal";
import { useChatStore } from "@/store/chat.store";

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const { clearChat } = useChatStore();
  const router = useRouter();
  const pathname = usePathname();
  const [showCreate, setShowCreate] = useState(false);
  const [showMenu,   setShowMenu]   = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [q,          setQ]          = useState("");
  const menuRef   = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // ... (Keep existing useEffects and search function) ...
  useEffect(() => {
    const fn = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setShowMenu(false); };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  useEffect(() => { if (showSearch) searchRef.current?.focus(); }, [showSearch]);

  const search = (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim()) { router.push(`/explore?q=${encodeURIComponent(q.trim())}`); setShowSearch(false); setQ(""); }
  };

  const score = user?.impact_score ?? 0;

  const links = [
    { href:"/",               icon:Home,          label:"Home" },
    { href:"/explore",        icon:Compass,       label:"Explore" },
    { href:"/events",         icon:CalendarCheck, label:"Events" },
    { href:"/leaderboard",    icon:Trophy,        label:"Leaderboard" },
    { href:"/notifications",  icon:Bell,          label:"Notifications" },
  ];

  // ✅ New handleLogout function to ensure both Auth and Chat are cleared
  const handleLogout = () => {
    clearChat(); // Wipe the bot's memory
    logout();    // Clear auth state
    router.push("/");
    setShowMenu(false);
  };

  const isLanding = pathname === "/";

  return (
    <>
      {/* ── Navbar shell ── */}
      <nav className={`fixed top-0 w-full z-50 h-14 isolate transition-colors duration-200 ${isLanding ? "bg-transparent border-b-0" : "bg-white border-b border-[#E3EBE9]"}`}>
        <div className="max-w-6xl mx-auto px-4 h-full flex items-center justify-between gap-3">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 shrink-0 group">
            <div className="w-8 h-8 rounded-xl bg-[#0F766E] flex items-center justify-center shadow-green group-hover:bg-[#0B5A54] transition-colors duration-150">
              <img src="./new.jpeg" alt="" className="w-8 h-8 rounded-xl object-cover" />
            </div>
            <span className={`font-display font-bold text-lg hidden sm:block tracking-tight transition-colors duration-200 ${isLanding ? "text-white" : "text-[#0E2A2B]"}`}>CivicImpact</span>
          </Link>

          {/* Centred search */}
          <form onSubmit={search} className="hidden md:flex flex-1 max-w-sm">
            <div className="relative w-full">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-5 w-5 text-[#4A6061]" strokeWidth={1.75} />
              <input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search people, causes…"
                className="w-full pl-10 pr-4 py-2 bg-[#F5F8F7] border border-[#E3EBE9] rounded-xl text-sm text-[#0E2A2B] placeholder-[#4A6061] outline-none
                           focus:bg-white focus:border-[#0F766E] focus:ring-2 focus:ring-[#DDF3EE] transition-all duration-150"
              />
            </div>
          </form>

          {/* Right icons */}
          <div className="flex items-center gap-0.5">
            {isAuthenticated ? (
              <>
                {/* Mobile search toggle */}
                <button
                  onClick={() => setShowSearch(!showSearch)}
                  className="md:hidden w-11 h-11 flex items-center justify-center rounded-xl hover:bg-[#F5F8F7] transition-colors duration-150 text-[#4A6061]"
                >
                  <Search className="h-5 w-5" strokeWidth={1.75} />
                </button>

                {/* Nav links */}
                {links.map(({ href, icon: Icon, label }) => {
                  const active = pathname === href;
                  return (
                    <Link
                      key={href}
                      href={href}
                      title={label}
                      className={cn(
                        "w-11 h-11 flex items-center justify-center rounded-xl transition-all duration-150 relative hidden sm:flex",
                        active
                          ? "bg-[#DDF3EE] text-[#0F766E]"
                          : "text-[#4A6061] hover:bg-[#F5F8F7] hover:text-[#0E2A2B]"
                      )}
                    >
                      <Icon className="h-5 w-5" strokeWidth={1.75} />
                      {active && (
                        <span className="absolute bottom-1.5 left-1/2 -translate-x-1/2 w-1 h-1 bg-[#0F766E] rounded-full" />
                      )}
                    </Link>
                  );
                })}

                {/* Create post */}
                <button
                  onClick={() => setShowCreate(true)}
                  className="w-11 h-11 flex items-center justify-center rounded-xl text-[#4A6061] hover:bg-[#F5F8F7] hover:text-[#0E2A2B] transition-all duration-150"
                >
                  <PlusSquare className="h-5 w-5" strokeWidth={1.75} />
                </button>

                {/* Avatar + dropdown */}
                <div className="relative ml-1" ref={menuRef}>
                  <button
                    onClick={() => setShowMenu(!showMenu)}
                    className="rounded-full focus:outline-none focus:ring-2 focus:ring-[#0F766E] focus:ring-offset-2 hover:opacity-90 transition-opacity ring-2 ring-[#E3EBE9]"
                  >
                    <Avatar src={user?.avatar?.url} name={user?.name} size="sm" />
                  </button>

                  {showMenu && (
                    <div className="absolute right-0 top-12 w-56 bg-white border border-[#E3EBE9] rounded-2xl shadow-medium overflow-hidden animate-scale-in z-50">
                      {/* Header */}
                      <div className="px-4 py-3 bg-[#F5F8F7] border-b border-[#E3EBE9]">
                        <p className="text-sm font-bold text-[#0E2A2B]">{user?.name}</p>
                        <p className="text-xs text-[#4A6061] mt-0.5">@{user?.username}</p>
                        <p className="text-xs text-[#0F766E] font-semibold mt-1">⚡ {score} impact pts</p>
                      </div>

                      {/* Menu Links */}
                      <Link
                        href={`/profile/${user?.username}`}
                        onClick={() => setShowMenu(false)}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#0E2A2B] hover:bg-[#F5F8F7] transition-colors duration-150"
                      >
                        <User className="h-5 w-5 text-[#4A6061]" strokeWidth={1.75} /> Profile
                      </Link>
                      <Link
                        href="/settings"
                        onClick={() => setShowMenu(false)}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#0E2A2B] hover:bg-[#F5F8F7] transition-colors duration-150"
                      >
                        <Settings className="h-5 w-5 text-[#4A6061]" strokeWidth={1.75} /> Settings
                      </Link>

                      {user?.role === "admin" && (
                        <Link
                          href="/admin/login"
                          onClick={() => setShowMenu(false)}
                          className="flex items-center gap-3 px-4 py-2.5 text-sm text-purple-600 hover:bg-purple-50 transition-colors duration-150"
                        >
                          <Settings className="h-5 w-5" strokeWidth={1.75} /> Admin Panel
                        </Link>
                      )}

                      <div className="border-t border-[#E3EBE9]" />

                      {/* ✅ Updated logout button */}
                      <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors duration-150 w-full"
                      >
                        <LogOut className="h-5 w-5" strokeWidth={1.75} /> Log out
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className={`text-sm font-medium px-3 py-1.5 transition-colors duration-150 ${isLanding ? "text-white/90 hover:text-white" : "text-[#4A6061] hover:text-[#0F766E]"}`}
                >
                  Log in
                </Link>
                <Link
                  href="/register"
                  className="text-sm font-semibold bg-[#0F766E] text-white px-4 py-1.5 rounded-xl hover:bg-[#0B5A54] transition-colors duration-150 shadow-green"
                >
                  Sign up
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ... Mobile Search ... */}
        {showSearch && (
          <div className="md:hidden absolute top-14 left-0 right-0 bg-white border-b border-[#E3EBE9] px-4 py-2 z-50">
            <form onSubmit={search} className="relative">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#4A6061]" strokeWidth={1.75} />
              <input
                ref={searchRef}
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Search people, causes…"
                className="w-full pl-10 pr-10 py-2 bg-[#F5F8F7] border border-[#E3EBE9] rounded-xl text-sm outline-none focus:border-[#0F766E] focus:ring-2 focus:ring-[#DDF3EE] transition-all"
              />
              <button type="button" onClick={() => setShowSearch(false)} className="absolute right-3 top-1/2 -translate-y-1/2">
                <X className="h-4 w-4 text-[#4A6061]" />
              </button>
            </form>
          </div>
        )}
      </nav>

      {showCreate && <CreatePostModal onClose={() => setShowCreate(false)} />}
    </>
  );
}
