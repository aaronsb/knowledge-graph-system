# Polarity Axis Triangulation Visualizations

These Python scripts demonstrate the **Polarity Axis Triangulation** approach from ADR-058 using matplotlib.

## Files

1. **`polarity_axis_visualization.py`** - 3D interactive visualization
   - Shows polarity pairs as colored spheres
   - Displays difference vectors between opposing pairs
   - Visualizes the averaged polarity axis in gold
   - Interactive sliders to move edge position
   - Real-time projection calculation

2. **`polarity_axis_2d_demo.py`** - 2D comparison and interactive demo
   - Side-by-side comparison: Old binary vs New continuous approach
   - Shows how multiple pairs create a robust axis
   - Interactive angle slider to explore projections
   - Clear visualization of grounding percentages

3. **`run_demo.py`** - Simple launcher script

## Requirements

```bash
pip install numpy matplotlib
```

## Usage

### Option 1: Run the launcher
```bash
python run_demo.py
```

### Option 2: Run individual scripts
```bash
python polarity_axis_visualization.py  # 3D demo
python polarity_axis_2d_demo.py        # 2D demos
```

## Key Concepts Demonstrated

### Old Binary Approach (Problems)
- Forces each edge into either SUPPORTS or CONTRADICTS bucket
- Results in binary extremes (-100%, 0%, or +100%)
- Loses nuance due to high similarity between prototypes (81%)

### New Polarity Axis Triangulation (Solution)
1. **Multiple Pairs**: Uses 5 opposing relationship pairs
   - SUPPORTS ↔ CONTRADICTS
   - VALIDATES ↔ REFUTES
   - CONFIRMS ↔ DISPROVES
   - REINFORCES ↔ OPPOSES
   - ENABLES ↔ PREVENTS

2. **Difference Vectors**: Calculates vectors from negative to positive pole

3. **Averaging**: Averages all difference vectors to find true semantic direction

4. **Projection**: Projects edge embeddings onto this axis using dot product

5. **Result**: Continuous grounding values that reflect semantic nuance

## Interactive Features

### 3D Visualization
- **Theta/Phi sliders**: Move edge position in 3D space
- **Animate button**: Rotate the 3D view
- **Mouse drag**: Manual camera control (if using interactive backend)

### 2D Interactive Demo
- **Angle slider**: Rotate edge vector around origin
- **Real-time updates**: See projection change continuously
- **Color coding**: Green (support), Red (contradict), Gray (neutral)

## Mathematical Formula

```
Polarity Axis = normalize(mean([E(p⁺ᵢ) - E(p⁻ᵢ) for all pairs i]))
Grounding = Σ(confidence × dot(edge_embedding, polarity_axis)) / Σ(confidence)
```

## Example Results

| Edge Type | Old Binary | New Projection |
|-----------|------------|----------------|
| MOUNTED_ON | +100% or -100% | +15% (slightly supportive) |
| PART_OF | +100% or -100% | +2% (nearly neutral) |
| SUPPORTS | +100% | +85% (strongly supportive) |
| CONTRADICTS | -100% | -78% (strongly contradictory) |

The new approach provides nuanced, interpretable grounding values instead of misleading binary extremes.
