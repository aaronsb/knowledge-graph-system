/**
 * User Profile Component
 *
 * Displays user authentication status with dropdown menu:
 * - Login button (when not authenticated)
 * - User info + logout (when authenticated)
 */

import React, { useState, useRef, useEffect } from 'react';
import { User, LogIn, LogOut, Shield, Moon, Sun, Sunset } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { LoginModal } from '../auth/LoginModal';
import { getZIndexClass } from '../../config/zIndex';

// Theme icon and label mapping
const THEME_CONFIG = {
  light: { icon: Sun, label: 'Light', next: 'Twilight' },
  twilight: { icon: Sunset, label: 'Twilight', next: 'Dark' },
  dark: { icon: Moon, label: 'Dark', next: 'Light' },
} as const;

export const UserProfile: React.FC = () => {
  const { user, isAuthenticated, isLoading, error, logout, clearError } = useAuthStore();
  const { appliedTheme, cycleTheme } = useThemeStore();
  const themeConfig = THEME_CONFIG[appliedTheme];
  const [isOpen, setIsOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Clear error when closing dropdown
  useEffect(() => {
    if (!isOpen && error) {
      clearError();
    }
  }, [isOpen, error, clearError]);

  const handleLogin = () => {
    setShowLoginModal(true);
  };

  const handleLogout = async () => {
    setIsOpen(false);
    await logout();
  };

  if (isLoading) {
    return (
      <button
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent text-accent-foreground"
        disabled
      >
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        <span>Loading...</span>
      </button>
    );
  }

  if (!isAuthenticated) {
    const ThemeIcon = themeConfig.icon;
    return (
      <>
        <div className="flex items-center gap-2">
          <button
            onClick={cycleTheme}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
            title={`${themeConfig.label} Mode (click for ${themeConfig.next})`}
          >
            <ThemeIcon className="w-4 h-4" />
          </button>
          <button
            onClick={handleLogin}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
            title="Login with OAuth 2.0"
          >
            <LogIn className="w-4 h-4" />
            <span>Login</span>
          </button>
        </div>
        <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
      </>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-accent hover:text-accent-foreground transition-colors"
        title={`Logged in as ${user?.username || 'user'}`}
      >
        <User className="w-4 h-4" />
        <span>{user?.username || 'User'}</span>
      </button>

      {isOpen && (
        <div className={`absolute right-0 mt-2 w-64 bg-background border border-border rounded-lg shadow-lg overflow-hidden ${getZIndexClass('userMenu')}`}>
          {/* User Info Header */}
          <div className="px-4 py-3 border-b border-border bg-accent">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                <User className="w-5 h-5 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{user?.username}</div>
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <Shield className="w-3 h-3" />
                  <span className="capitalize">{user?.role || 'User'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}

          {/* Status Info */}
          <div className="px-4 py-2 text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>Authentication:</span>
              <span className="text-status-active">OAuth 2.0</span>
            </div>
            <div className="flex justify-between mt-1">
              <span>Status:</span>
              <span className="text-status-active">Connected</span>
            </div>
          </div>

          {/* Actions */}
          <div className="border-t border-border">
            <button
              onClick={cycleTheme}
              className="w-full flex items-center gap-2 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors text-left"
            >
              <themeConfig.icon className="w-4 h-4" />
              <span>{themeConfig.label} Mode</span>
              <span className="text-xs text-muted-foreground ml-auto">→ {themeConfig.next}</span>
            </button>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors text-left"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
