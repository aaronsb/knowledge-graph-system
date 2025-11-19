/**
 * Confirm Dialog Component
 *
 * A themed modal dialog for confirmations, replacing native window.confirm().
 * Supports single confirm, save-before-action, and custom button configurations.
 */

import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Info, HelpCircle } from 'lucide-react';

type DialogVariant = 'confirm' | 'warning' | 'info';

interface DialogButton {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'destructive';
  autoFocus?: boolean;
}

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  message: string;
  variant?: DialogVariant;
  buttons: DialogButton[];
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  onClose,
  title,
  message,
  variant = 'confirm',
  buttons,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Focus trap and auto-focus
  useEffect(() => {
    if (isOpen && dialogRef.current) {
      const autoFocusButton = dialogRef.current.querySelector('[data-autofocus]') as HTMLButtonElement;
      if (autoFocusButton) {
        autoFocusButton.focus();
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const Icon = variant === 'warning' ? AlertTriangle : variant === 'info' ? Info : HelpCircle;
  const iconColor = variant === 'warning' ? 'text-yellow-500' : variant === 'info' ? 'text-blue-500' : 'text-muted-foreground';

  const getButtonClasses = (btnVariant?: string) => {
    const base = 'px-4 py-2 text-sm font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2';

    switch (btnVariant) {
      case 'primary':
        return `${base} bg-primary text-primary-foreground hover:bg-primary/90 focus:ring-primary`;
      case 'destructive':
        return `${base} bg-destructive text-destructive-foreground hover:bg-destructive/90 focus:ring-destructive`;
      default:
        return `${base} bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground focus:ring-ring`;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className="relative bg-card border border-border rounded-lg shadow-lg max-w-md w-full mx-4 p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
      >
        <div className="flex items-start gap-4">
          <div className={`flex-shrink-0 ${iconColor}`}>
            <Icon className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h3 id="dialog-title" className="text-lg font-semibold mb-2">
              {title}
            </h3>
            <p className="text-sm text-muted-foreground">
              {message}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          {buttons.map((button, index) => (
            <button
              key={index}
              onClick={button.onClick}
              className={getButtonClasses(button.variant)}
              data-autofocus={button.autoFocus || undefined}
            >
              {button.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

/**
 * Hook to manage confirm dialog state
 */
interface UseConfirmDialogReturn {
  isOpen: boolean;
  show: (config: Omit<ConfirmDialogProps, 'isOpen' | 'onClose'>) => Promise<boolean>;
  dialogProps: ConfirmDialogProps;
}

export function useConfirmDialog(): UseConfirmDialogReturn {
  const [isOpen, setIsOpen] = React.useState(false);
  const [config, setConfig] = React.useState<Omit<ConfirmDialogProps, 'isOpen' | 'onClose'>>({
    title: '',
    message: '',
    buttons: [],
  });
  const resolveRef = React.useRef<(value: boolean) => void>();

  const show = React.useCallback(
    (newConfig: Omit<ConfirmDialogProps, 'isOpen' | 'onClose'>): Promise<boolean> => {
      return new Promise((resolve) => {
        resolveRef.current = resolve;
        setConfig(newConfig);
        setIsOpen(true);
      });
    },
    []
  );

  const onClose = React.useCallback(() => {
    setIsOpen(false);
    resolveRef.current?.(false);
  }, []);

  const dialogProps: ConfirmDialogProps = {
    ...config,
    isOpen,
    onClose,
  };

  return { isOpen, show, dialogProps };
}