#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify that the environment is set up correctly.
This script checks for the required dependencies and creates a sample flood map.
"""

import os
import sys
import importlib
import subprocess

def check_dependency(package):
    """Check if a package is installed."""
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False

def main():
    # List of required packages
    required_packages = [
        'geopandas',
        'rasterio',
        'matplotlib',
        'numpy',
        'osmnx',
        'shapely',
        'folium',
        'tqdm'
    ]
    
    # Check for required packages
    missing_packages = []
    for package in required_packages:
        if not check_dependency(package):
            missing_packages.append(package)
    
    if missing_packages:
        print("Error: The following required packages are missing:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install them using:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("All required packages are installed.")
    
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Created 'data' directory.")
    
    # Create output directories if they don't exist
    for dir_path in ['output', 'output/static_maps', 'output/data']:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created '{dir_path}' directory.")
    
    # Create a sample flood map
    sample_path = 'data/sample_flood_depth.tif'
    if not os.path.exists(sample_path):
        print("Creating sample flood depth map...")
        try:
            from prepare_flood_map import create_sample_flood_map
            create_sample_flood_map(sample_path)
        except Exception as e:
            print(f"Error creating sample flood map: {e}")
            print("Trying to run the prepare_flood_map.py script directly...")
            try:
                subprocess.run([sys.executable, 'src/prepare_flood_map.py', 'sample', sample_path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error running prepare_flood_map.py: {e}")
                return False
    
    # Reclassify the sample flood map
    categories_path = 'data/sample_flood_categories.tif'
    if not os.path.exists(categories_path):
        print("Reclassifying sample flood map...")
        try:
            from prepare_flood_map import reclassify_flood_map
            reclassify_flood_map(sample_path, categories_path)
        except Exception as e:
            print(f"Error reclassifying flood map: {e}")
            print("Trying to run the prepare_flood_map.py script directly...")
            try:
                subprocess.run([sys.executable, 'src/prepare_flood_map.py', 'reclassify', sample_path, categories_path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error running prepare_flood_map.py: {e}")
                return False
    
    print("\nSetup completed successfully!")
    print("\nYou can now run the flood impact analysis using:")
    print(f"python src/run_example.py {categories_path}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)