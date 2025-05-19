# Quick Start Guide

This guide will help you quickly get started with the Flood Impact Mapping tool.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a sample flood map for testing:
```bash
python src/prepare_flood_map.py sample data/sample_flood_depth.tif
```

3. Reclassify the sample flood map to categorical values:
```bash
python src/prepare_flood_map.py reclassify data/sample_flood_depth.tif data/sample_flood_categories.tif
```

## Running the Analysis

Run the flood impact analysis using the sample map:
```bash
python src/run_example.py data/sample_flood_categories.tif
```

## Viewing Results

After running the analysis, you can find the results in the `output` directory:

1. Open `output/flood_impact_map.html` in a web browser to view the interactive map
2. Check `output/static_maps/` for static visualizations
3. Explore `output/data/` for GeoJSON files that can be imported into GIS software

## Using Your Own Data

To use your own flood depth data:

1. Prepare your GeoTIFF flood depth map
2. Reclassify it to categorical values:
```bash
python src/prepare_flood_map.py reclassify path/to/your/flood_depth.tif path/to/output/flood_categories.tif
```
3. Run the analysis:
```bash
python src/flood_impact_mapper.py path/to/output/flood_categories.tif
```

## Customizing the Analysis

You can customize the analysis by specifying different infrastructure types or adjusting the search distance:

```bash
python src/flood_impact_mapper.py path/to/flood_map.tif --infrastructure hospital school police --search-distance 15
```

## Troubleshooting

If you encounter issues:

1. Ensure your GeoTIFF has the correct format (categorical values 0-4)
2. Check that the GeoTIFF has a valid coordinate reference system (CRS)
3. For large areas, the OpenStreetMap API might rate-limit requests. Try analyzing smaller areas or adding delays between requests.

For more detailed information, refer to the full README.md file. 