# Polarity Axis Analysis Visualization

**Status:** Proposed
**Date:** 2025-11-30
**Context:** ADR-070 Web UI Enhancement

## Problem Statement

The Polarity Axis Analysis produces rich multidimensional data that currently displays only as text statistics and lists. Users need to visually understand:

- How concepts distribute across the polarity axis
- The correlation between position and grounding strength
- Clustering patterns and outliers
- The overall "shape" of the semantic dimension

## Research Findings

### Established Visualization Patterns

1. **Semantic Differential Scales** ([Vizzlo](https://vizzlo.com/create/semantic-differential-scale), [AYTM](https://aytm.com/post/semantic-differential-scale-measuring-perceptions-and-attitudes-of-your-brand))
   - Classic method for bipolar dimensions (since 1950s)
   - Typically shows single dimension as profile chart
   - Our challenge: multiple concepts to display simultaneously

2. **Scatter Plots for Correlation** ([Atlassian](https://www.atlassian.com/data/charts/what-is-a-scatter-plot), [Flourish](https://flourish.studio/visualisations/scatter-charts/))
   - Standard visualization for correlation analysis
   - Shows relationship between two continuous variables
   - Best practice includes regression line, interactive tooltips

3. **Bubble Charts for Multidimensional Data** ([Chartio](https://chartio.com/learn/charts/bubble-chart-complete-guide/), [Storytelling with Data](https://www.storytellingwithdata.com/blog/2021/5/11/what-is-a-bubble-chart))
   - Encode 3-4 dimensions: x-position, y-position, size, color
   - Human cognition limit: ~4 visual dimensions ([source](https://www.storytellingwithdata.com/blog/2021/5/11/what-is-a-bubble-chart))
   - Optimal match for our data structure

4. **Interactive Features** ([R Psychologist](https://rpsychologist.com/correlation/), [Number Analytics](https://www.numberanalytics.com/blog/data-visualization-for-correlation))
   - Tooltips showing details on hover
   - Zoom/pan for exploration
   - Filtering and brushing
   - Linked views between visualizations

## Available Data Dimensions

From each analysis we have:

**Per-Concept:**
- Position on axis: -1 (negative pole) to +1 (positive pole)
- Grounding strength: continuous value (can be negative)
- Direction label: positive, neutral, negative
- Axis distance: how well concept fits the dimension
- Concept label and ID

**Aggregate Statistics:**
- Pearson r (correlation coefficient)
- p-value (significance)
- Mean position
- Distribution by direction
- Regression line parameters (can derive from r and data)

## Proposed Visualization System

### Primary: Bubble Chart Scatter Plot

**Visual Encoding:**

| Dimension | Encoding | Rationale |
|-----------|----------|-----------|
| Position on axis | X-axis (-1 to +1) | Natural mapping to polarity dimension |
| Grounding strength | Y-axis | Primary variable of interest for correlation |
| Direction category | Color | Immediate visual grouping (blue/gray/orange) |
| Axis distance (fit) | Bubble size | Larger = better fit to dimension |
| Correlation trend | Regression line overlay | Shows correlation visually |

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  Grounding                                              │
│  Strength    o  ● O    Regression Line                 │
│      ↑     ●  O  o  ●     /                            │
│      │   o  ●    o   ●  /                              │
│      │  O   ● o    O  /●                               │
│      │ ●  o  O  ●  o/                                  │
│      │o  ●  O  ● o/                                    │
│      └──────────────────────────→                      │
│         -1    Neutral    +1                            │
│    Negative Pole    Position    Positive Pole          │
│                                                         │
│  Legend:                                               │
│  ● Positive  o Neutral  ● Negative                     │
│  Size = Relevance to axis                              │
└─────────────────────────────────────────────────────────┘
```

**Interactive Features:**
- **Hover**: Tooltip shows concept label, exact position, grounding, axis distance
- **Click**: Highlight concept, dim others
- **Zoom/Pan**: Explore dense regions
- **Filter**: Toggle direction categories on/off

### Secondary: Distribution Histogram

Shows concept distribution across the axis (below or beside scatter plot).

```
┌─────────────────────────────────────────────────────────┐
│  Count                                                  │
│    ↑   ┌──┐                                            │
│    │   │  │     ┌──┐                                   │
│    │┌──┤  │  ┌──┤  │  ┌──┐                            │
│    ││  │  │  │  │  │  │  │                            │
│    └──────────────────────────────→                    │
│      -1    Neutral    +1                               │
│                                                         │
│  Stacked by direction:                                 │
│  ■ Positive  □ Neutral  ■ Negative                     │
└─────────────────────────────────────────────────────────┘
```

### Tertiary: Statistics Summary Panel

Visual hierarchy of key metrics (could be beside or above chart):

```
┌──────────────────────────────────────┐
│  Correlation: r = 0.82  ●●●●○        │
│                p < 0.01  (confident) │
│                                      │
│  Balance: ──────●───────             │
│           -1    0.07   +1            │
│           (slightly positive-leaning) │
│                                      │
│  Concepts: 9 ■ 9 □ 0 ■               │
│           Pos Neu Neg                │
└──────────────────────────────────────┘
```

## Implementation Considerations

### Technology Options

**Recharts** (Recommended for Phase 1):
- Good React integration
- Declarative API
- Built-in responsive design
- Supports bubble charts, tooltips, zoom
- **Trade-off:** Less customization than D3

**Victory**:
- More customizable
- Better animation support
- Steeper learning curve

**D3.js**:
- Maximum flexibility
- Full control over interactions
- Requires more development time
- Better for novel visualizations

**Recommendation:** Start with Recharts for rapid implementation, migrate to D3 if we need custom interactions later.

### Color Palette

Using existing Polarity Explorer colors:
- **Positive pole concepts:** `text-blue-500` (#3B82F6)
- **Neutral concepts:** `text-muted-foreground` (gray)
- **Negative pole concepts:** `text-orange-500` (#F97316)

With opacity for overlapping bubbles: 0.6-0.8 alpha

### Size Scaling

Axis distance ranges from 0 (perfect fit) to potentially >2 (unrelated).

Inverse mapping for bubble size:
- Distance 0.0-0.5: Large bubbles (12-20px radius)
- Distance 0.5-1.0: Medium bubbles (8-12px radius)
- Distance >1.0: Small bubbles (4-8px radius)

### Performance

With typical analysis of 10-50 concepts:
- Scatter plot: No performance concerns
- Histogram: Fast to compute and render
- Interactive features: Debounce hover events

For future scaling to 100+ concepts:
- Consider canvas rendering instead of SVG
- Implement virtualization or clustering
- Add overview+detail pattern

## User Benefits

This visualization enables users to immediately answer:

1. **"Do concepts cluster or spread evenly?"** → Visual density in scatter plot
2. **"Is the correlation strong?"** → Slope of regression line, visual trend
3. **"Which side has better evidence?"** → Y-axis distribution, regression direction
4. **"Are there interesting outliers?"** → Bubbles far from regression line
5. **"How balanced is the axis?"** → X-axis distribution, mean position marker
6. **"Which concepts are most relevant?"** → Larger bubbles

## Next Steps

1. Create proof-of-concept scatter plot with mock data
2. Integrate with actual analysis results
3. Add interactive features (tooltips, filtering)
4. User testing for clarity and insights
5. Refine based on feedback
6. Add distribution histogram
7. Add statistics summary panel

## Open Questions

1. Should we show pole labels on the chart itself or rely on surrounding context?
2. Do we need a "reference" or "baseline" visualization for comparison across queries?
3. Should axis distance be encoded as size or as a secondary metric (e.g., border thickness)?
4. How do we handle extreme outliers (grounding >> 1 or << -1)?
5. Would users benefit from exporting the visualization as PNG/SVG?

## References

- [Semantic Differential Scale Maker](https://vizzlo.com/create/semantic-differential-scale) - Established bipolar visualization
- [Mastering Scatter Plots](https://www.atlassian.com/data/charts/what-is-a-scatter-plot) - Best practices
- [Bubble Chart Complete Guide](https://chartio.com/learn/charts/bubble-chart-complete-guide/) - Multidimensional encoding
- [What is a Bubble Chart](https://www.storytellingwithdata.com/blog/2021/5/11/what-is-a-bubble-chart) - Cognitive limits
- [Interactive Scatter Charts](https://flourish.studio/visualisations/scatter-charts/) - Modern examples
- [Understanding Correlations](https://rpsychologist.com/correlation/) - Interactive demo
- [Data Visualization for Correlation](https://www.numberanalytics.com/blog/data-visualization-for-correlation/) - Analysis techniques
