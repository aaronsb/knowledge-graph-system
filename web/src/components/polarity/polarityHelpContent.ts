/**
 * Help content for Polarity Explorer
 */

export interface PolarityHelpTopic {
  id: string;
  title: string;
  category: 'concept' | 'statistics' | 'usage';
  description: string;
  interpretation?: string[];
  tips?: string[];
  example?: string;
}

export const polarityHelpContent: Record<string, PolarityHelpTopic> = {
  overview: {
    id: 'overview',
    title: 'Polarity Axis Analysis',
    category: 'concept',
    description:
      'Polarity Axis Analysis projects concepts onto a bidirectional semantic dimension formed by two opposing poles (e.g., Modern ↔ Traditional, Centralized ↔ Distributed). This reveals where concepts fall on the spectrum between the poles and uncovers patterns in how concepts relate to opposing ideas.',
    interpretation: [
      'Concepts near the positive pole align strongly with that perspective',
      'Concepts near the negative pole align strongly with the opposite perspective',
      'Neutral concepts are balanced between both poles or orthogonal to the axis',
      'Axis distance shows how closely a concept aligns with the dimension itself',
    ],
    tips: [
      'Choose poles that represent genuine opposites or extremes',
      'Start with max_hops=1 for focused analysis, increase to 2 for broader context',
      'Look for concepts clustered near poles vs. scattered in the middle',
      'Check grounding correlation to see if one pole has stronger evidence',
    ],
    example:
      'Analyzing "Modern Tools ↔ Traditional Operating Models" reveals which concepts lean toward innovation vs. established practices.',
  },

  pearsonR: {
    id: 'pearsonR',
    title: 'Pearson r (Correlation Coefficient)',
    category: 'statistics',
    description:
      'Measures the linear relationship between axis position and grounding strength. Values range from -1 to +1.',
    interpretation: [
      'r > 0.7: Strong positive correlation - concepts toward positive pole have higher grounding',
      'r > 0.4: Moderate positive correlation',
      '|r| < 0.3: Weak or no correlation',
      'r < -0.4: Moderate negative correlation',
      'r < -0.7: Strong negative correlation - concepts toward negative pole have higher grounding',
    ],
    tips: [
      'Strong correlation suggests the axis has an inherent value judgment',
      'Weak correlation suggests a descriptive axis without bias toward either pole',
      'Negative correlation means the "negative" pole is actually better grounded',
    ],
    example:
      'r = 0.82 for "Evidence-Based ↔ Speculative" would show evidence-based concepts have stronger grounding (as expected).',
  },

  pValue: {
    id: 'pValue',
    title: 'p-value (Statistical Significance)',
    category: 'statistics',
    description:
      'Probability that the observed correlation occurred by chance. Lower values indicate more reliable correlations.',
    interpretation: [
      'p < 0.01: Very strong evidence of correlation (highly significant)',
      'p < 0.05: Strong evidence of correlation (statistically significant)',
      'p < 0.10: Moderate evidence (marginally significant)',
      'p ≥ 0.10: Weak or no evidence (not significant)',
    ],
    tips: [
      'Only trust correlation strength (Pearson r) when p-value is low (< 0.05)',
      'High p-value means the pattern might be random noise',
      'Requires sufficient data: at least 10-20 concepts for reliable p-values',
    ],
    example:
      'p = 0.03 with r = 0.65 means the moderate correlation is statistically significant and likely real.',
  },

  meanPosition: {
    id: 'meanPosition',
    title: 'Mean Position',
    category: 'statistics',
    description:
      'Average position of all projected concepts on the axis. Range: -1 (toward negative pole) to +1 (toward positive pole), with 0 as the midpoint.',
    interpretation: [
      'Mean ≈ 0: Balanced distribution between poles',
      'Mean > 0.2: Concepts skew toward positive pole',
      'Mean < -0.2: Concepts skew toward negative pole',
      'Extreme mean (> 0.5 or < -0.5): Very unbalanced, one pole dominates',
    ],
    tips: [
      'Check if skew matches your expectations about the domain',
      'Unbalanced mean might indicate poles of different scope or importance',
      'Compare with direction distribution to see clustering patterns',
    ],
    example:
      'Mean = -0.35 for "Innovation ↔ Stability" suggests the graph contains more stability-focused concepts.',
  },

  axisDistance: {
    id: 'axisDistance',
    title: 'Axis Distance',
    category: 'statistics',
    description:
      'How far a concept is from the axis itself (orthogonal distance). Lower values mean the concept aligns strongly with the semantic dimension; higher values mean the concept is tangential or unrelated.',
    interpretation: [
      'Distance < 0.5: Concept strongly aligns with the axis dimension',
      'Distance 0.5-1.0: Moderate alignment',
      'Distance > 1.0: Concept is somewhat orthogonal or unrelated to the axis',
    ],
    tips: [
      'High axis distance concepts might not fit the polarity well',
      'Filter out high-distance concepts to focus on aligned ones',
      'Compare distances to assess axis quality',
    ],
    example:
      'A concept with position=0.2 and distance=1.2 is only weakly related to the axis dimension.',
  },

  groundingCorrelation: {
    id: 'groundingCorrelation',
    title: 'Grounding Correlation',
    category: 'statistics',
    description:
      'The relationship between where concepts fall on the axis and how well-supported they are by evidence (grounding strength). Reveals whether one pole is more grounded than the other.',
    interpretation: [
      'Strong positive: Positive pole concepts have better evidence',
      'Strong negative: Negative pole concepts have better evidence',
      'Weak or none: Both poles equally grounded (descriptive axis)',
    ],
    tips: [
      'Strong correlation suggests an inherent value judgment in the axis',
      'Weak correlation indicates a neutral, descriptive dimension',
      'Check p-value to confirm the correlation is real',
      'Can reveal bias in the knowledge graph toward one perspective',
    ],
    example:
      'Strong negative correlation for "Modern ↔ Traditional" might show traditional concepts have more historical evidence.',
  },

  projectedConcepts: {
    id: 'projectedConcepts',
    title: 'Projected Concepts',
    category: 'concept',
    description:
      'Concepts discovered via graph traversal and projected onto the polarity axis. Each concept has a position (-1 to +1), direction (positive/neutral/negative), grounding strength, and axis distance.',
    interpretation: [
      'Position: Where the concept falls between the poles',
      'Direction: Categorical grouping based on position thresholds',
      'Grounding: Evidence strength (positive = well-supported, negative = contradicted)',
      'Axis distance: How well the concept fits the dimension',
    ],
    tips: [
      'Sort by position to see the spectrum from negative to positive',
      'Group by direction to find clusters',
      'Look for synthesis concepts in the neutral zone',
      'High-grounding neutral concepts might bridge both perspectives',
    ],
    example:
      'A neutral concept with high grounding might represent a synthesis idea that combines both poles.',
  },

  usageScenarios: {
    id: 'usageScenarios',
    title: 'Usage Scenarios',
    category: 'usage',
    description: 'Common patterns and what they mean:',
    interpretation: [
      'Balanced distribution (equal positive/negative/neutral): The axis captures a genuine spectrum with diverse perspectives',
      'Heavy clustering toward one pole: The knowledge graph is biased toward one perspective, or poles are unequal in scope',
      'Mostly neutral concepts: The poles might be too similar, or concepts are orthogonal to the axis',
      'Strong grounding correlation: One pole has inherently better evidence (value-laden axis)',
      'Weak grounding correlation: Descriptive axis without inherent bias',
      'High axis distances overall: Poles might not form a coherent semantic dimension',
    ],
    tips: [
      'Use for semantic exploration: discover conceptual spectrums',
      'Find synthesis concepts: high-grounding neutral concepts',
      'Validate relationships: check if related concepts cluster as expected',
      'Pedagogical ordering: arrange concepts from one pole to the other',
      'Identify bias: strong grounding correlation reveals value judgments',
    ],
  },
};

export const polarityHelpCategories = {
  concept: 'Concepts & Theory',
  statistics: 'Statistical Measures',
  usage: 'Usage & Interpretation',
};
