/**
 * Z-Index Layer Management
 *
 * Centralized z-index constants to prevent layering conflicts.
 * Lower values appear behind higher values.
 *
 * USAGE:
 *   import { getZIndexClass, getZIndexValue } from '@/config/zIndex';
 *
 *   // In component className (recommended):
 *   <div className={`fixed ${getZIndexClass('userMenu')}`}>...</div>
 *
 *   // In inline styles (when needed):
 *   <div style={{ zIndex: getZIndexValue('userMenu') }}>...</div>
 *
 * Layer organization (lowest to highest):
 * - Content layer (10-19): Main content elements
 * - Overlay layer (20-29): Search bars, toolbars
 * - Dropdown layer (30-39): Dropdown menus, tooltips
 * - Modal layer (40-49): Modals, dialogs, top-level menus
 * - Notification layer (50+): Critical notifications, toasts
 *
 * IMPORTANT: When adding new z-index values here, you MUST also add them to
 * web/tailwind.config.js theme.extend.zIndex for Tailwind JIT compilation.
 */

export const Z_INDEX = {
  // Content layer - Main visualization and content
  content: 10,

  // Overlay layer - Toolbars, search bars, panels
  toolbar: 20,
  searchBar: 25,

  // Dropdown layer - Dropdowns, popovers, tooltips
  dropdown: 30,
  searchResults: 35,

  // Modal layer - Dialogs, modals, and top-level menus
  userMenu: 40,
  modalOverlay: 45,
  modal: 50,

  // Notification layer - Critical UI elements
  notification: 60,
  toast: 70,
} as const;

/**
 * Helper function to get Tailwind z-index class
 * @param layer - The z-index layer name
 * @returns Tailwind z-index class string
 *
 * @example
 * getZIndexClass('userMenu') // returns 'z-40'
 */
export const getZIndexClass = (layer: keyof typeof Z_INDEX): string => {
  return `z-${Z_INDEX[layer]}`;
};

/**
 * Helper function to get inline style z-index value
 * @param layer - The z-index layer name
 * @returns Numeric z-index value
 *
 * @example
 * getZIndexValue('userMenu') // returns 40
 */
export const getZIndexValue = (layer: keyof typeof Z_INDEX): number => {
  return Z_INDEX[layer];
};
