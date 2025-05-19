#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Example script to demonstrate how to use the FloodImpactMapper.
This script assumes you have a GeoTIFF flood map in the data directory.
"""

import os
import sys
import argparse
from flood_impact_mapper import FloodImpactMapper

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run flood impact mapping example')
    parser.add_argument('flood_map', type=str, help='Path to the GeoTIFF flood map')
    parser.add_argument('--output-dir', type=str, default='output', help='Directory to save output files')
    parser.add_argument('--scientific-map', type=str, help='Filename for the scientific publication-quality map')
    args = parser.parse_args()
    
    # Check if the flood map file exists
    if not os.path.exists(args.flood_map):
        print(f"Error: Flood map file '{args.flood_map}' not found.")
        sys.exit(1)
    
    # Define output directory
    output_dir = args.output_dir
    
    # Define infrastructure categories to analyze
    infrastructure_categories = [
        'Healthcare',
        'Emergency Services',
        'Shelter and Facilities',
        'Transportation',
        'Utilities'
    ]
    
    print(f"Analyzing flood impacts for categories: {', '.join(infrastructure_categories)}")
    print(f"Using flood map: {args.flood_map}")
    print(f"Output will be saved to: {output_dir}")
    
    # Create and run the flood impact mapper
    mapper = FloodImpactMapper(
        flood_map_path=args.flood_map,
        output_dir=output_dir,
        search_distance=10.0  # 10 meters search distance
    )
    
    # Run the analysis
    mapper.run(infrastructure_categories, args.scientific_map)

if __name__ == "__main__":
    main() 