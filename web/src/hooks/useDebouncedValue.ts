import { useEffect, useState } from 'react';

/**
 * Debounce a value by the specified delay
 *
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 500ms)
 * @returns The debounced value
 *
 * @example
 * const searchQuery = 'user input';
 * const debouncedQuery = useDebouncedValue(searchQuery, 300);
 * // debouncedQuery only updates 300ms after searchQuery stops changing
 */
export function useDebouncedValue<T>(value: T, delay: number = 500): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
