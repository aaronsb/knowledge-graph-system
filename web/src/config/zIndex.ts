/**
 * Z-Index Layer Management
 *
 * Centralized z-index constants to prevent layering conflicts.
 * Lower values appear behind higher values.
 *
 * Layer organization (lowest to highest):
 * - Base layer (0-9): Default document flow
 * - Content layer (10-19): Main content elements
 * - Overlay layer (20-29): Search bars, toolbars
 * - Dropdown layer (30-39): Dropdown menus, tooltips
 * - Modal layer (40-49): Modals, dialogs
 * - Notification layer (50+): Critical notifications, toasts
 */

export const Z_INDEX = {
  // Base layer - Default elements
  base: 0,

  // Content layer - Main visualization and content
  content: 10,

  // Overlay layer - Toolbars, search bars, panels
  toolbar: 20,
  searchBar: 25,

  // Dropdown layer - Dropdowns, popovers, tooltips
  dropdown: 30,
  searchResults: 35,
  userMenu: 40,

  // Modal layer - Dialogs and modals
  modal: 50,
  modalOverlay: 45,

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
