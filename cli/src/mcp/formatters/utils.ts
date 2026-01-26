/**
 * Shared utilities for MCP formatters
 */

/**
 * Format grounding strength as text (token-efficient)
 * This is the fallback when grounding_display is not available.
 */
export function formatGroundingStrength(grounding: number): string {
  const groundingValue = grounding.toFixed(3);
  const percentValue = grounding * 100;

  // Use ≈ symbol when value is very close to zero but not exactly zero
  const groundingPercent = (Math.abs(percentValue) < 0.1 && percentValue !== 0)
    ? `≈${percentValue >= 0 ? '0' : '-0'}`
    : percentValue.toFixed(0);

  let level: string;
  if (grounding >= 0.7) level = 'Strong';
  else if (grounding >= 0.3) level = 'Moderate';
  else if (grounding >= 0) level = 'Weak';
  else if (grounding >= -0.3) level = 'Negative';
  else level = 'Contradicted';

  return `${level} (${groundingValue}, ${groundingPercent}%)`;
}

/**
 * Format grounding with confidence-awareness (grounding × confidence two-dimensional model)
 *
 * Uses grounding_display when available (categorical label from API).
 * Includes numeric confidence_score alongside the label for quantitative insight.
 * Falls back to raw grounding score display for backwards compatibility.
 */
export function formatGroundingWithConfidence(
  grounding: number | undefined | null,
  groundingDisplay: string | undefined | null,
  confidenceScore: number | undefined | null = null
): string {
  // Format confidence score as percentage if available
  const confScoreStr = confidenceScore !== undefined && confidenceScore !== null
    ? ` [${(confidenceScore * 100).toFixed(0)}% conf]`
    : '';

  // If we have a grounding_display label from the API, use it directly
  if (groundingDisplay) {
    return `${groundingDisplay}${confScoreStr}`;
  }

  // Fall back to raw grounding score display if available
  if (grounding !== undefined && grounding !== null) {
    return formatGroundingStrength(grounding);
  }

  // No grounding information available
  return 'Unexplored';
}
