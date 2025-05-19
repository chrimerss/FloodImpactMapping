#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility script to prepare GeoTIFF flood maps for use with the FloodImpactMapper.
This script can convert continuous depth values to categorical flood levels.
"""

import os
import argparse
import numpy as np
import rasterio
from rasterio.transform import from_origin
import matplotlib.pyplot as plt


def reclassify_flood_map(input_path, output_path, depth_thresholds=None):
    """
    Reclassify a continuous flood depth map to categorical flood levels.
    
    Parameters:
    -----------
    input_path : str
        Path to the input GeoTIFF flood depth map
    output_path : str
        Path to save the output categorical GeoTIFF
    depth_thresholds : list
        List of depth thresholds in meters [nuisance, minor, moderate, major]
        Default: [0.1, 0.2, 0.5, 1.0]
    """
    if depth_thresholds is None:
        depth_thresholds = [0.1, 0.2, 0.5, 1.0]
    
    # Ensure we have 4 thresholds
    if len(depth_thresholds) != 4:
        raise ValueError("Must provide exactly 4 depth thresholds")
    
    # Open the input raster
    with rasterio.open(input_path) as src:
        # Read the data
        data = src.read(1)
        
        # Create a copy of the metadata
        meta = src.meta.copy()
        
        # Reclassify the data
        # 0: No Flood (< threshold[0])
        # 1: Nuisance Flood (threshold[0] - threshold[1])
        # 2: Minor Flood (threshold[1] - threshold[2])
        # 3: Moderate Flood (threshold[2] - threshold[3])
        # 4: Major Flood (> threshold[3])
        
        # Start with all zeros (no flood)
        classified = np.zeros_like(data, dtype=np.uint8)
        
        # Apply thresholds
        classified = np.where(data >= depth_thresholds[0], 1, classified)  # Nuisance
        classified = np.where(data >= depth_thresholds[1], 2, classified)  # Minor
        classified = np.where(data >= depth_thresholds[2], 3, classified)  # Moderate
        classified = np.where(data >= depth_thresholds[3], 4, classified)  # Major
        
        # Update metadata for the output raster
        meta.update(
            dtype=rasterio.uint8,
            count=1,
            nodata=255
        )
        
        # Write the output raster
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(classified, 1)
    
    print(f"Reclassified flood map saved to {output_path}")
    
    # Create a visualization of the reclassified map
    create_preview(output_path, output_path.replace('.tif', '_preview.png'))


def create_preview(raster_path, output_path):
    """
    Create a preview image of the reclassified flood map.
    
    Parameters:
    -----------
    raster_path : str
        Path to the reclassified GeoTIFF
    output_path : str
        Path to save the preview image
    """
    # Define colors for flood categories
    colors = {
        0: (1.0, 1.0, 1.0),  # White for no flood
        1: (1.0, 0.8, 0.8),  # Light red
        2: (1.0, 0.5, 0.5),  # Medium red
        3: (1.0, 0.0, 0.0),  # Dark red
        4: (0.5, 0.0, 0.5)   # Purple
    }
    
    # Create a custom colormap
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([colors[i] for i in range(5)])
    
    # Open the raster
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        
        # Create the figure
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot the data
        im = ax.imshow(data, cmap=cmap, vmin=0, vmax=4)
        
        # Add a colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_ticks([0, 1, 2, 3, 4])
        cbar.set_ticklabels([
            'No Flood',
            'Nuisance (0.1-0.2m)',
            'Minor (0.2-0.5m)',
            'Moderate (0.5-1.0m)',
            'Major (>1.0m)'
        ])
        
        # Set title and labels
        plt.title('Reclassified Flood Map')
        plt.xlabel('Column')
        plt.ylabel('Row')
        
        # Save the figure
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    print(f"Preview image saved to {output_path}")


def create_sample_flood_map(output_path, width=500, height=500):
    """
    Create a sample flood depth map for testing purposes.
    
    Parameters:
    -----------
    output_path : str
        Path to save the sample GeoTIFF
    width : int
        Width of the raster in pixels
    height : int
        Height of the raster in pixels
    """
    # Create a sample flood depth array
    # This creates a radial gradient with maximum depth in the center
    y, x = np.ogrid[-height/2:height/2, -width/2:width/2]
    distance = np.sqrt(x*x + y*y)
    
    # Normalize distance to 0-1 range
    max_distance = np.sqrt((width/2)**2 + (height/2)**2)
    normalized_distance = distance / max_distance
    
    # Create depth values (inverse of distance from center)
    # Maximum depth of 2.0 meters at the center
    depth = 2.0 * (1 - normalized_distance)
    
    # Add some random variation
    np.random.seed(42)
    noise = np.random.normal(0, 0.1, (height, width))
    depth += noise
    
    # Clip negative values to 0
    depth = np.clip(depth, 0, None)
    
    # Create a simple transform (1 meter per pixel)
    transform = from_origin(0, height, 1, 1)
    
    # Define metadata
    meta = {
        'driver': 'GTiff',
        'height': height,
        'width': width,
        'count': 1,
        'dtype': rasterio.float32,
        'crs': '+proj=utm +zone=10 +datum=WGS84 +units=m +no_defs',
        'transform': transform,
        'nodata': -9999
    }
    
    # Write the raster
    with rasterio.open(output_path, 'w', **meta) as dst:
        dst.write(depth.astype(np.float32), 1)
    
    print(f"Sample flood depth map saved to {output_path}")
    
    # Create a preview of the sample map
    create_depth_preview(output_path, output_path.replace('.tif', '_preview.png'))


def create_depth_preview(raster_path, output_path):
    """
    Create a preview image of a flood depth map.
    
    Parameters:
    -----------
    raster_path : str
        Path to the flood depth GeoTIFF
    output_path : str
        Path to save the preview image
    """
    # Open the raster
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        
        # Create the figure
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot the data with a blue colormap
        im = ax.imshow(data, cmap='Blues', vmin=0)
        
        # Add a colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Flood Depth (meters)')
        
        # Set title and labels
        plt.title('Flood Depth Map')
        plt.xlabel('Column')
        plt.ylabel('Row')
        
        # Save the figure
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    print(f"Depth preview image saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Prepare GeoTIFF flood maps for analysis')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Reclassify command
    reclassify_parser = subparsers.add_parser('reclassify', help='Reclassify a continuous flood depth map')
    reclassify_parser.add_argument('input', type=str, help='Path to input flood depth GeoTIFF')
    reclassify_parser.add_argument('output', type=str, help='Path to save output categorical GeoTIFF')
    reclassify_parser.add_argument('--thresholds', type=float, nargs=4, 
                                 default=[0.1, 0.2, 0.5, 1.0],
                                 help='Depth thresholds in meters [nuisance, minor, moderate, major]')
    
    # Sample command
    sample_parser = subparsers.add_parser('sample', help='Create a sample flood depth map')
    sample_parser.add_argument('output', type=str, help='Path to save sample GeoTIFF')
    sample_parser.add_argument('--width', type=int, default=500, help='Width of the raster in pixels')
    sample_parser.add_argument('--height', type=int, default=500, help='Height of the raster in pixels')
    
    args = parser.parse_args()
    
    if args.command == 'reclassify':
        reclassify_flood_map(args.input, args.output, args.thresholds)
    elif args.command == 'sample':
        create_sample_flood_map(args.output, args.width, args.height)
    else:
        parser.print_help()


if __name__ == '__main__':
    main() 