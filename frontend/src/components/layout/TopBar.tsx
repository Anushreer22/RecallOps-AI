import React, { useState, useRef, useEffect } from 'react';
import {
  Building2,
  FolderKanban,
  Sun,
  Moon,
  LogOut,
  ChevronDown,
  Search,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { Badge } from '../ui/Badge';

export const TopBar: React.FC = () => {
  const { user, activeOrg, activeProject, role, switchOrganization, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const orgRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (orgRef.current && !orgRef.current.contains(e.target as Node)) {
        setOrgDropdownOpen(false);
      }
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="h-16 border-b border-slate-800 bg-[#090d16]/90 backdrop-blur sticky top-0 z-30 flex items-center justify-between px-6">
      {/* Left: Organization & Project Scopes */}
      <div className="flex items-center gap-3">
        {/* Organization Switcher */}
        <div className="relative" ref={orgRef}>
          <button
            onClick={() => setOrgDropdownOpen(!orgDropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-900 border border-slate-800 rounded-md hover:bg-slate-800/80 transition"
          >
            <Building2 className="w-3.5 h-3.5 text-indigo-400" />
            <span className="max-w-[130px] truncate">
              {activeOrg?.organization_name || 'Select Org'}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {orgDropdownOpen && user?.memberships && (
            <div className="absolute left-0 mt-1.5 w-60 bg-slate-900 border border-slate-800 rounded-lg shadow-xl shadow-black/80 py-1.5 z-40">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                Organizations
              </div>
              {user.memberships.map((m) => (
                <button
                  key={m.organization_id}
                  onClick={() => {
                    switchOrganization(m.organization_id);
                    setOrgDropdownOpen(false);
                  }}
                  className={`flex items-center justify-between w-full px-3 py-2 text-xs text-left hover:bg-slate-800/70 transition ${
                    activeOrg?.organization_id === m.organization_id
                      ? 'text-indigo-400 font-semibold bg-indigo-950/20'
                      : 'text-slate-300'
                  }`}
                >
                  <span className="truncate">{m.organization_name}</span>
                  <Badge variant="role" value={m.role} />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Project Context Badge / Display */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md">
          <FolderKanban className="w-3.5 h-3.5 text-slate-400" />
          <span className="truncate max-w-[120px]">
            {activeProject?.name || 'All Projects'}
          </span>
        </div>
      </div>

      {/* Middle: Search Box */}
      <div className="hidden md:flex items-center w-80">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search incidents, services, error codes... (Ctrl+K)"
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900/80 border border-slate-800 rounded-md text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
          />
        </div>
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3">
        {/* Role Badge */}
        {role && <Badge variant="role" value={role} />}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-md transition"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* User Profile Dropdown */}
        <div className="relative" ref={userRef}>
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center gap-2 p-1.5 text-xs text-slate-300 hover:text-slate-100 hover:bg-slate-800/60 rounded-md transition"
          >
            <div className="flex items-center justify-center w-7 h-7 rounded-full bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 font-semibold text-xs">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="hidden sm:inline font-medium max-w-[100px] truncate">
              {user?.full_name}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {userDropdownOpen && (
            <div className="absolute right-0 mt-1.5 w-56 bg-slate-900 border border-slate-800 rounded-lg shadow-xl shadow-black/80 py-2 z-40">
              <div className="px-4 py-2 border-b border-slate-800">
                <p className="text-xs font-semibold text-slate-100 truncate">{user?.full_name}</p>
                <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
              </div>
              <div className="py-1">
                <button
                  onClick={logout}
                  className="flex items-center gap-2 w-full px-4 py-2 text-xs text-rose-400 hover:bg-slate-800/80 transition text-left"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
