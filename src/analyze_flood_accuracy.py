#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import pandas as pd
import numpy as np
from tqdm import tqdm
from shapely.geometry import box, mapping

def load_claims(claims_dir):
    """
    Load and combine FEMA claims data from both auto and property claims.
    
    Parameters:
    -----------
    claims_dir : str
        Directory containing the FEMA claims shapefiles
        
    Returns:
    --------
    GeoDataFrame
        Combined claims data with geometry and claim information
    """
    print("Loading FEMA claims data...")
    
    # Load auto claims
    auto_claims_path = os.path.join(claims_dir, 'FEMA_Harvey2017_AutoClaims_Aug25_Sep08.shp')
    auto_claims = gpd.read_file(auto_claims_path).to_crs(epsg=4326)
    
    # Load property claims
    property_claims_path = os.path.join(claims_dir, 'FEMA_Harvey2017_PropertyClaims_Aug25_Sep08.shp')
    property_claims = gpd.read_file(property_claims_path).to_crs(epsg=4326)
    
    # Combine claims
    all_claims = pd.concat([auto_claims, property_claims], ignore_index=True)
    
    print(f"Loaded {len(auto_claims)} auto claims and {len(property_claims)} property claims")
    return all_claims

def check_flood_at_point(point, flood_src, search_distance=1e-5):
    """
    Check if a point is in a flooded area by looking at the maximum flood category
    within a search distance.
    
    Parameters:
    -----------
    point : shapely.geometry.Point
        The point to check
    flood_src : rasterio.DatasetReader
        The flood map raster
    search_distance : float
        Search distance in degrees (approximately 10 meters in EPSG:4326)
        
    Returns:
    --------
    int
        Maximum flood category found within search distance (0 if no flood)
    """
    try:
        # Convert point to flood map CRS
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326").to_crs(flood_src.crs)
        point_geom = point_gdf.geometry.values[0]
        
        # Create a buffer around the point
        buffer = point_geom.buffer(search_distance)
        
        # Get row, col in the raster for the point
        x, y = point_geom.x, point_geom.y
        row, col = rasterio.transform.rowcol(flood_src.transform, x, y)
        
        # Check if point is within raster bounds
        if (0 <= row < flood_src.height and 0 <= col < flood_src.width):
            # Get flood category at point
            flood_value = flood_src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
            
            # If point has flood, return its category
            if flood_value > 0:
                return int(flood_value)
        
        # If point is not in raster or has no flood, check within buffer
        
            # Mask the raster with the buffer
        masked_data, _ = mask(flood_src, [mapping(buffer)], crop=True, nodata=0)
        
        # Get the maximum flood category within the buffer
        max_value = int(np.max(masked_data))
        
        # Return the maximum flood category if it's valid
        if max_value > 0:
            return max_value
        else:
            return 0  # No flood found
                
        
    except Exception as e:
        print(f"Error checking flood at point: {e}")
        return 0

def filter_unique_features(claims_gdf, precision=1e-5):
    """
    Filter out repetitive features by rounding coordinates and keeping unique locations.
    
    Parameters:
    -----------
    claims_gdf : GeoDataFrame
        Input claims data
    precision : float
        Precision for rounding coordinates
        
    Returns:
    --------
    GeoDataFrame
        Filtered claims with unique locations
    """
    # Round coordinates to specified precision
    claims_gdf['rounded_x'] = claims_gdf.geometry.x.round(decimals=int(-np.log10(precision)))
    claims_gdf['rounded_y'] = claims_gdf.geometry.y.round(decimals=int(-np.log10(precision)))
    
    # Keep only unique locations
    unique_claims = claims_gdf.drop_duplicates(subset=['rounded_x', 'rounded_y'])
    
    # Drop temporary columns
    unique_claims = unique_claims.drop(columns=['rounded_x', 'rounded_y'])
    
    print(f"Filtered {len(claims_gdf) - len(unique_claims)} repetitive features")
    return unique_claims

def analyze_flood_accuracy(flood_map_path, claims_gdf):
    """
    Analyze how many claims are covered by the flood simulation.
    
    Parameters:
    -----------
    flood_map_path : str
        Path to the flood map GeoTIFF
    claims_gdf : GeoDataFrame
        FEMA claims data
        
    Returns:
    --------
    dict
        Dictionary containing accuracy metrics
    """
    print(f"\nAnalyzing flood map: {os.path.basename(flood_map_path)}")
    
    # Open flood map
    with rasterio.open(flood_map_path) as flood_src:
        # Get flood map bounds
        bounds = flood_src.bounds
        flood_bbox = gpd.GeoDataFrame(
            geometry=[box(bounds.left, bounds.bottom, bounds.right, bounds.top)],
            crs=flood_src.crs
        )
        
        # Convert claims to flood map CRS and crop to flood map bounds
        claims_crs = claims_gdf.to_crs(flood_src.crs)
        claims_cropped = gpd.overlay(claims_crs, flood_bbox, how='intersection')
        
        # Filter unique features
        claims_unique = filter_unique_features(claims_cropped)
        
        # Initialize counters
        total_claims = len(claims_unique)
        covered_claims = 0
        flood_categories = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}  # Count claims by flood category
        
        if total_claims == 0:
            print("No claims found within flood map bounds")
            return {
                'total_claims': 0,
                'covered_claims': 0,
                'accuracy': 0,
                'flood_categories': flood_categories
            }
        
        # Check each claim
        for idx, claim in tqdm(claims_unique.iterrows(), total=total_claims, desc="Processing claims"):
            flood_cat = check_flood_at_point(claim.geometry, flood_src, search_distance=2e-5)
            flood_categories[flood_cat] += 1
            if flood_cat > 0:
                covered_claims += 1
        
        # Calculate accuracy metrics
        accuracy = covered_claims / total_claims if total_claims > 0 else 0
        
        return {
            'total_claims': total_claims,
            'covered_claims': covered_claims,
            'accuracy': accuracy,
            'flood_categories': flood_categories
        }

def main():
    # Define paths
    claims_dir = '../FEMA_Harvey2017_Claims_shp'
    flood_maps_pattern = '../data/HOU00*_500yr.tif'
    
    # Find all flood maps
    flood_maps = glob.glob(flood_maps_pattern)
    if not flood_maps:
        print(f"No flood maps found matching pattern: {flood_maps_pattern}")
        return
    
    # Load claims data
    claims_gdf = load_claims(claims_dir)
    
    # Analyze each flood map
    results = []
    for flood_map in flood_maps:
        result = analyze_flood_accuracy(flood_map, claims_gdf)
        result['flood_map'] = os.path.basename(flood_map)
        results.append(result)
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Expand flood categories into separate columns
    flood_cats_df = pd.DataFrame([r['flood_categories'] for r in results])
    results_df = pd.concat([
        results_df.drop('flood_categories', axis=1),
        flood_cats_df
    ], axis=1)
    
    # Save results
    output_file = 'flood_accuracy_analysis.csv'
    results_df.to_csv(output_file, index=False)
    print(f"\nResults saved to {output_file}")
    
    # Print summary
    print("\nSummary of flood simulation accuracy:")
    print(results_df.to_string(index=False))

if __name__ == '__main__':
    main() 