/**
 * Help content for Polarity Explorer
 */

export interface PolarityHelpTopic {
  id: string;
  title: string;
  category: 'concept' | 'statistics' | 'usage';
  description: string; // Friendly, approachable explanation
  technicalDescription?: string; // Technical details (collapsible)
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
    title: 'Correlation Strength (Pearson r)',
    category: 'statistics',
    description:
      'Think of this as asking: "Do concepts on one side of the axis tend to have better evidence than the other?" A positive number means concepts toward the positive pole are better supported by evidence. A negative number means the opposite pole has stronger backing. A number close to zero means both sides are about equally grounded.',
    technicalDescription:
      'Pearson\'s correlation coefficient (r) measures the linear relationship between axis position and grounding strength. Values range from -1 (perfect negative correlation) to +1 (perfect positive correlation), with 0 indicating no linear relationship.',
    interpretation: [
      'Strong positive (r > 0.7): Concepts leaning toward the positive pole have much better evidence',
      'Moderate positive (r > 0.4): Positive pole concepts tend to have better evidence',
      'Weak or none (|r| < 0.3): Both sides have similar quality of evidence',
      'Moderate negative (r < -0.4): Negative pole concepts tend to have better evidence',
      'Strong negative (r < -0.7): Concepts leaning toward the negative pole have much better evidence',
    ],
    tips: [
      'A strong correlation hints that one perspective inherently has more evidence in your knowledge base',
      'A weak correlation means the axis is descriptive - neither side is "better", just different',
      'Don\'t be surprised if the "negative" pole has positive correlation - the labels are arbitrary!',
    ],
    example:
      'For "Evidence-Based ↔ Speculative": r = 0.82 means evidence-based concepts are, unsurprisingly, better grounded in evidence.',
  },

  pValue: {
    id: 'pValue',
    title: 'Confidence Level (p-value)',
    category: 'statistics',
    description:
      'This tells you: "Can I trust this pattern, or might it just be a coincidence?" A low p-value (under 0.05) means you can trust the correlation. A high p-value means the pattern might just be random luck - like seeing faces in clouds.',
    technicalDescription:
      'The p-value represents the probability that the observed correlation could have occurred by random chance. It\'s calculated using the t-distribution based on the correlation coefficient and sample size. Lower values provide stronger evidence against the null hypothesis of no correlation.',
    interpretation: [
      'p < 0.01: Very confident - this pattern is almost certainly real',
      'p < 0.05: Confident - this pattern is probably real (standard threshold)',
      'p < 0.10: Somewhat confident - there might be something here',
      'p ≥ 0.10: Not confident - could easily be random noise',
    ],
    tips: [
      'Always check p-value before trusting the correlation number',
      'With few concepts (< 10), even strong correlations might have high p-values',
      'Think of it as a "trust meter" for the correlation strength',
    ],
    example:
      'If r = 0.65 and p = 0.03: The correlation is moderate AND trustworthy. If r = 0.65 and p = 0.40: The correlation looks moderate but might just be coincidence.',
  },

  meanPosition: {
    id: 'meanPosition',
    title: 'Average Balance',
    category: 'statistics',
    description:
      'This shows which side most concepts lean toward, on average. Think of it like asking your friend group their opinion: if most lean one way, the average will tilt that direction. Zero means perfectly balanced. Positive means more concepts lean toward the positive pole. Negative means they lean toward the negative pole.',
    technicalDescription:
      'The mean position is the arithmetic average of all concept positions on the normalized axis. The scale ranges from -1 (toward negative pole) to +1 (toward positive pole), with 0 representing the exact midpoint between poles.',
    interpretation: [
      'Near 0 (±0.2): Balanced - concepts are spread fairly evenly',
      'Positive (> 0.2): Tilted toward positive pole - that perspective is more common',
      'Negative (< -0.2): Tilted toward negative pole - that perspective is more common',
      'Extreme (> 0.5 or < -0.5): Very one-sided - one perspective dominates heavily',
    ],
    tips: [
      'Ask yourself: does this match what you expected? If not, why might that be?',
      'A tilt might mean one perspective is more popular, or just better documented',
      'Compare with how many concepts fall in each direction for the full picture',
    ],
    example:
      'Mean = -0.35 for "Innovation ↔ Stability" means your knowledge base has more stability-focused concepts. Maybe because stable practices get documented more?',
  },

  axisDistance: {
    id: 'axisDistance',
    title: 'Relevance to This Comparison',
    category: 'statistics',
    description:
      'Some concepts just don\'t fit neatly on your chosen axis - they\'re talking about something else entirely. This measures how "on topic" each concept is. Low distance means the concept really relates to your poles. High distance means it\'s kind of tangential or off in its own world.',
    technicalDescription:
      'Axis distance measures the orthogonal (perpendicular) distance from the concept\'s embedding vector to the polarity axis in high-dimensional space. It represents how much of the concept\'s semantic meaning is unexplained by the polarity dimension.',
    interpretation: [
      'Low (< 0.5): This concept is clearly about your polarity - it fits well',
      'Medium (0.5-1.0): Somewhat related but has other dimensions too',
      'High (> 1.0): This concept is mostly about other things - tangentially related at best',
    ],
    tips: [
      'Concepts with high distance might be interesting outliers worth investigating',
      'If many concepts have high distance, your poles might not form a clear dimension',
      'Low distance concepts are the "pure examples" of your polarity',
    ],
    example:
      'For "Modern ↔ Traditional": a concept about "Software Updates" might have low distance (clearly fits). But "Coffee Preferences"? High distance - not really about modernity vs tradition.',
  },

  groundingCorrelation: {
    id: 'groundingCorrelation',
    title: 'Evidence Quality Pattern',
    category: 'statistics',
    description:
      'Here\'s a fun question: does one side of your axis have better evidence than the other? This looks at whether concepts on one pole are better-supported by sources and data. It can reveal hidden biases - like if "new ideas" consistently have less evidence than "traditional practices" just because old stuff has been documented longer.',
    technicalDescription:
      'Grounding correlation is the Pearson correlation coefficient between axis position and grounding strength scores. It quantifies whether there is a systematic relationship between a concept\'s position on the polarity axis and the quality/quantity of evidence supporting it.',
    interpretation: [
      'Strong positive: The positive pole side has consistently better evidence',
      'Strong negative: The negative pole side has consistently better evidence',
      'Weak or none: Evidence quality is independent of which side concepts lean toward',
    ],
    tips: [
      'This can reveal whether your axis has an implicit value judgment baked in',
      'Historical vs. modern axes often show correlation due to documentation age',
      'A neutral correlation means you\'re comparing apples to apples in terms of evidence',
      'Strong correlation might reflect real-world bias in documentation, not reality',
    ],
    example:
      'For "Experimental ↔ Proven Methods": if proven methods have higher grounding (negative correlation), that makes sense - they\'ve been documented more. But if experimental has higher grounding, maybe your knowledge base is from cutting-edge research!',
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
