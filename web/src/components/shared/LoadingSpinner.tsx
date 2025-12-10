/**
 * LoadingSpinner - Classic Unix-style text spinner
 *
 * The timeless -\|/ spinner that's been used in CLIs forever.
 * Clean, technical, and wobble-free.
 */

import React, { useState, useEffect } from 'react';

interface LoadingSpinnerProps {
  className?: string;
}

const SPINNER_FRAMES = ['—', '\\', '|', '/'];

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ className = '' }) => {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame((f) => (f + 1) % SPINNER_FRAMES.length);
    }, 100);
    return () => clearInterval(interval);
  }, []);

  return (
    <span className={`font-mono inline-block w-3 text-center ${className}`}>
      {SPINNER_FRAMES[frame]}
    </span>
  );
};
