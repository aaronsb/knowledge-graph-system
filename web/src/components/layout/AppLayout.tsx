/**
 * Main Application Layout
 *
 * Provides the workstation structure:
 * - Sidebar with collapsible category navigation
 * - Main content area
 *
 * Navigation categories per ADR-067:
 * - Explorers (2D, 3D, etc.)
 * - Block Editor
 * - Ingest
 * - Jobs
 * - Report
 * - Edit
 * - Admin
 */

import React, { useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Compass,
  Blocks,
  Upload,
  ListTodo,
  FileText,
  PencilLine,
  Settings,
  Shield,
  Network,
  Box,
  GitBranch,
  FlaskConical,
  Home,
  Waypoints,
  PieChart,
  Layers,
  AlertTriangle,
  X,
} from 'lucide-react';
import { UserProfile } from '../shared/UserProfile';
import { SidebarCategory, SidebarItem } from './SidebarCategory';
import { GraphAnimation } from '../home/GraphAnimation';
import { AboutInfoBox } from './AboutInfoBox';
import { isInsecureCryptoMode } from '../../lib/auth/authorization-code-flow';

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [aboutBox, setAboutBox] = useState<{ x: number; y: number } | null>(null);
  const [dismissedInsecureWarning, setDismissedInsecureWarning] = useState(false);

  // Check if running in insecure crypto mode (dev only, tree-shaken in prod)
  const showInsecureWarning = import.meta.env.DEV && isInsecureCryptoMode() && !dismissedInsecureWarning;

  // Handle right-click on branding area to show About box
  const handleBrandingContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setAboutBox({ x: e.clientX, y: e.clientY });
  }, []);

  // Determine active item from current path
  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  // Get current workspace name for toolbar
  const getWorkspaceName = () => {
    const path = location.pathname;
    if (path === '/') return 'Home';
    if (path.startsWith('/explore/2d')) return '2D Force Graph';
    if (path.startsWith('/explore/3d')) return '3D Force Graph';
    if (path.startsWith('/explore/documents')) return 'Document Explorer';
    if (path.startsWith('/blocks')) return 'Block Editor';
    if (path.startsWith('/ingest')) return 'Ingest';
    if (path.startsWith('/jobs')) return 'Jobs';
    if (path.startsWith('/report')) return 'Report';
    if (path.startsWith('/polarity')) return 'Polarity Explorer';
    if (path.startsWith('/embeddings')) return 'Embedding Landscape';
    if (path === '/vocabulary') return 'Edge Explorer';
    if (path.startsWith('/vocabulary/chord')) return 'Vocabulary Analysis';
    if (path.startsWith('/edit')) return 'Edit';
    if (path.startsWith('/preferences')) return 'Preferences';
    if (path.startsWith('/admin')) return 'Admin';
    return 'Knowledge Graph';
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Sidebar - Workstation Navigation */}
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        <div
          className="p-4 border-b border-border relative overflow-hidden cursor-pointer"
          onContextMenu={handleBrandingContextMenu}
        >
          {/* Animated graph background */}
          <div className="absolute inset-0 opacity-30">
            <GraphAnimation
              width={256}
              height={80}
              interactive={true}
            />
          </div>
          {/* Branding text */}
          <h1 className="text-xl font-bold relative z-10">Knowledge Graph</h1>
          <p className="text-sm text-muted-foreground relative z-10">Workstation</p>
        </div>

        <nav className="flex-1 p-2 overflow-y-auto">
          {/* Home */}
          <div className="mb-2">
            <SidebarItem
              icon={Home}
              label="Home"
              description="Welcome & overview"
              isActive={isActive('/')}
              onClick={() => navigate('/')}
            />
          </div>

          {/* Explorers */}
          <SidebarCategory title="Explorers" icon={Compass} defaultExpanded={true}>
            <SidebarItem
              icon={Network}
              label="2D Force Graph"
              description="Interactive 2D visualization"
              isActive={isActive('/explore/2d')}
              onClick={() => navigate('/explore/2d')}
            />
            <SidebarItem
              icon={Box}
              label="3D Force Graph"
              description="Immersive 3D exploration"
              isActive={isActive('/explore/3d')}
              onClick={() => navigate('/explore/3d')}
            />
            <SidebarItem
              icon={FileText}
              label="Document Explorer"
              description="Radial document→concept view"
              isActive={isActive('/explore/documents')}
              onClick={() => navigate('/explore/documents')}
            />
            <SidebarItem
              icon={GitBranch}
              label="Polarity Explorer"
              description="Bidirectional semantic dimensions"
              isActive={isActive('/polarity')}
              onClick={() => navigate('/polarity')}
            />
            <SidebarItem
              icon={Layers}
              label="Embedding Landscape"
              description="3D t-SNE projection of concepts"
              isActive={isActive('/embeddings')}
              onClick={() => navigate('/embeddings')}
            />
            <SidebarItem
              icon={Waypoints}
              label="Edge Explorer"
              description="System-wide vocabulary analysis"
              isActive={isActive('/vocabulary') && !location.pathname.includes('/chord')}
              onClick={() => navigate('/vocabulary')}
            />
            <SidebarItem
              icon={PieChart}
              label="Vocabulary Analysis"
              description="Query-specific vocabulary breakdown"
              isActive={isActive('/vocabulary/chord')}
              onClick={() => navigate('/vocabulary/chord')}
            />
          </SidebarCategory>

          {/* Block Editor */}
          <SidebarCategory title="Block Editor" icon={Blocks} defaultExpanded={false}>
            <SidebarItem
              icon={Blocks}
              label="Flow Editor"
              description="Visual query builder"
              isActive={isActive('/blocks')}
              onClick={() => navigate('/blocks')}
            />
          </SidebarCategory>

          {/* Ingest */}
          <SidebarCategory title="Ingest" icon={Upload} defaultExpanded={false}>
            <SidebarItem
              icon={Upload}
              label="Upload Content"
              description="Import documents and URLs"
              isActive={isActive('/ingest')}
              onClick={() => navigate('/ingest')}
            />
          </SidebarCategory>

          {/* Jobs */}
          <SidebarCategory title="Jobs" icon={ListTodo} defaultExpanded={false}>
            <SidebarItem
              icon={ListTodo}
              label="Job Queue"
              description="Monitor extraction jobs"
              isActive={isActive('/jobs')}
              onClick={() => navigate('/jobs')}
            />
          </SidebarCategory>

          {/* Report */}
          <SidebarCategory title="Report" icon={FileText} defaultExpanded={false}>
            <SidebarItem
              icon={FileText}
              label="Data Export"
              description="Tabular views and exports"
              isActive={isActive('/report')}
              onClick={() => navigate('/report')}
            />
          </SidebarCategory>

          {/* Analysis - Reserved for vocabulary analysis tools */}
          {/* <SidebarCategory title="Analysis" icon={FlaskConical} defaultExpanded={false}>
          </SidebarCategory> */}

          {/* Edit */}
          <SidebarCategory title="Edit" icon={PencilLine} defaultExpanded={false}>
            <SidebarItem
              icon={PencilLine}
              label="Graph Editor"
              description="Manual node/edge editing"
              isActive={isActive('/edit')}
              onClick={() => navigate('/edit')}
            />
          </SidebarCategory>

          {/* Preferences */}
          <SidebarCategory title="Preferences" icon={Settings} defaultExpanded={false}>
            <SidebarItem
              icon={Settings}
              label="Settings"
              description="Theme, profile, appearance"
              isActive={isActive('/preferences')}
              onClick={() => navigate('/preferences')}
            />
          </SidebarCategory>

          {/* Admin */}
          <SidebarCategory title="Admin" icon={Shield} defaultExpanded={false}>
            <SidebarItem
              icon={Shield}
              label="Administration"
              description="Users, OAuth, system status"
              isActive={isActive('/admin')}
              onClick={() => navigate('/admin')}
            />
          </SidebarCategory>
        </nav>

        <div className="p-4 border-t border-border">
          <div className="text-xs text-muted-foreground">
            API: localhost:8000
          </div>
        </div>
      </aside>

      {/* About Info Box (shown on right-click in branding area) */}
      {aboutBox && (
        <AboutInfoBox
          x={aboutBox.x}
          y={aboutBox.y}
          onDismiss={() => setAboutBox(null)}
        />
      )}

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Insecure Crypto Warning Banner (DEV only) */}
        {showInsecureWarning && (
          <div className="bg-amber-500/90 text-black px-4 py-2 flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span className="font-medium">INSECURE CRYPTO MODE</span>
              <span className="opacity-80">
                — Using plain PKCE (no SHA-256) due to non-HTTPS context. Development only!
              </span>
            </div>
            <button
              onClick={() => setDismissedInsecureWarning(true)}
              className="p-1 hover:bg-black/10 rounded"
              title="Dismiss warning"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Toolbar */}
        <header className="h-14 border-b border-border bg-card px-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="font-semibold">{getWorkspaceName()}</h2>
          </div>

          <UserProfile />
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  );
};
