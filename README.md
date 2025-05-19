# Flood Impact Mapping

A Python tool to map the impact of floods on critical infrastructure and road networks using GeoTIFF flood maps and OpenStreetMap data.

## Overview

This project analyzes the impact of floods on critical infrastructure (hospitals, schools, etc.) and road networks. It takes a categorized GeoTIFF flood map as input and assigns flood severity categories to infrastructure and roads based on their proximity to flooded areas.

The flood categories are:
- 0: No Flood
- 1: Nuisance Flood (0.1-0.2m)
- 2: Minor Flood (0.2-0.5m)
- 3: Moderate Flood (0.5-1.0m)
- 4: Major Flood (>1.0m)

## Features

- Load and process GeoTIFF flood maps
- Query OpenStreetMap for road networks and critical infrastructure
- Assign flood categories to infrastructure and roads
- Generate interactive web maps with color-coded flood impacts
- Create static maps for visualization
- Export data to GeoJSON format for further analysis

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/FloodImpactMapping.git
cd FloodImpactMapping
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python src/flood_impact_mapper.py path/to/flood_map.tif
```

### Advanced Usage

```bash
python src/flood_impact_mapper.py path/to/flood_map.tif --output-dir results --search-distance 15 --infrastructure hospital school police grocery
```

### Command-line Arguments

- `flood_map`: Path to the GeoTIFF flood map (required)
- `--output-dir`: Directory to save output files (default: 'output')
- `--search-distance`: Distance in meters to search for flood values around infrastructure (default: 10.0)
- `--infrastructure`: Types of infrastructure to analyze (default: hospital, school, fire_station, police, grocery, pharmacy, fuel)

### Preparing Flood Maps

The project includes a utility script to help prepare GeoTIFF flood maps:

#### Create a Sample Flood Map

```bash
python src/prepare_flood_map.py sample data/sample_flood_depth.tif
```

#### Reclassify a Continuous Flood Depth Map

```bash
python src/prepare_flood_map.py reclassify data/flood_depth.tif data/flood_categories.tif --thresholds 0.1 0.2 0.5 1.0
```

### Example

```bash
python src/run_example.py path/to/flood_map.tif
```

## Output

The tool generates the following outputs in the specified output directory:

1. Interactive map (`flood_impact_map.html`): A web-based map showing flood impacts on infrastructure and roads
2. Static maps in the `static_maps` directory:
   - `infrastructure_flood_impact.png`: Map of affected infrastructure
   - `road_flood_impact.png`: Map of affected road network
3. GeoJSON data in the `data` directory:
   - `infrastructure_flood_impact.geojson`: Infrastructure data with flood categories
   - `road_flood_impact.geojson`: Road network data with flood categories

## Requirements

- Python 3.7+
- GeoPandas
- Rasterio
- OSMnx
- Folium
- Matplotlib
- NumPy
- Shapely
- tqdm

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
