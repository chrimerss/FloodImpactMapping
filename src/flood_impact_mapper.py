#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from shapely.geometry import Point, box, mapping
import osmnx as ox
import matplotlib.pyplot as plt
import folium
from folium.plugins import MarkerCluster
from shapely.ops import nearest_points
from tqdm import tqdm
import pandas as pd
from PIL import Image
import json

class FloodImpactMapper:
    def __init__(self, flood_map_path, output_dir="output", search_distance=10):
        """
        Initialize the FloodImpactMapper.
        
        Parameters:
        -----------
        flood_map_path : str
            Path to the GeoTIFF flood map
        output_dir : str
            Directory to save output files
        search_distance : float
            Distance in meters to search for flood values around infrastructure
        """
        self.flood_map_path = flood_map_path
        self.output_dir = output_dir
        self.search_distance = search_distance
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Load flood map
        self.load_flood_map()
        
        # Load critical infrastructure definitions
        self.load_infrastructure_definitions()
        
        # Define flood categories
        self.flood_categories = {
            0: "No Flood",
            1: "Nuisance Flood (0.1-0.2m)",
            2: "Minor Flood (0.2-0.5m)",
            3: "Moderate Flood (0.5-1.0m)",
            4: "Major Flood (>1.0m)"
        }
        
        # Define colors for flood categories
        self.flood_colors = {
            0: "#D3D3D3",  # Gray for no flood
            1: "#FFC8C8",  # Light red
            2: "#FF8080",  # Medium red
            3: "#FF0000",  # Dark red
            4: "#800080"   # Purple
        }

    def load_infrastructure_definitions(self):
        """Load critical infrastructure definitions from JSON file"""
        try:
            with open('critical_infrastructure_query.geojson', 'r') as f:
                data = json.load(f)
                # Get the infrastructure definitions from the top-level key
                self.infrastructure_definitions = data["Critical Infrastructures (Flooding Impact on Wellness)"]
            print("Loaded critical infrastructure definitions")
        except Exception as e:
            print(f"Error loading infrastructure definitions: {e}")
            self.infrastructure_definitions = {}

    def load_flood_map(self):
        """Load the flood map GeoTIFF file"""
        try:
            self.flood_src = rasterio.open(self.flood_map_path)
            self.flood_data = self.flood_src.read(1)
            self.flood_transform = self.flood_src.transform
            self.flood_crs = self.flood_src.crs
            
            # Get bounding box of the flood map
            self.bounds = box(*self.flood_src.bounds)
            self.bounds_gdf = gpd.GeoDataFrame({'geometry': [self.bounds]}, crs=self.flood_crs)
            
            # Convert bounds to WGS84 (EPSG:4326) for OSM queries
            self.bounds_wgs84 = self.bounds_gdf.to_crs(epsg=4326)
            self.north = self.bounds_wgs84.bounds.maxy.values[0]
            self.south = self.bounds_wgs84.bounds.miny.values[0]
            self.east = self.bounds_wgs84.bounds.maxx.values[0]
            self.west = self.bounds_wgs84.bounds.minx.values[0]
            
            print(f"Flood map loaded with bounds: N={self.north}, S={self.south}, E={self.east}, W={self.west}")
            print(f"Flood map CRS: {self.flood_crs}")
            
        except Exception as e:
            print(f"Error loading flood map: {e}")
            raise

    def get_flood_category_at_point(self, point):
        """
        Get the flood category at a specific point or within search_distance.
        
        Parameters:
        -----------
        point : shapely.geometry.Point
            The point to check for flooding
            
        Returns:
        --------
        int
            Flood category (0-4)
        """
        # Convert point to flood map CRS
        point_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326").to_crs(self.flood_crs)
        point_geom = point_gdf.geometry.values[0]
        
        # Create a buffer around the point
        buffer = point_geom.buffer(self.search_distance)
        
        # Get row, col in the raster for the point
        x, y = point_geom.x, point_geom.y
        row, col = rasterio.transform.rowcol(self.flood_transform, x, y)
        
        # Check if point is within raster bounds
        if (0 <= row < self.flood_data.shape[0] and 0 <= col < self.flood_data.shape[1]):
            # Get flood category at point
            point_value = self.flood_data[row, col]
            
            # If the point has a valid flood value, return it
            if point_value in self.flood_categories:
                return int(point_value)
        
        # If point is not in raster or has no value, check within buffer
        try:
            # Mask the raster with the buffer
            masked_data, _ = mask(self.flood_src, [mapping(buffer)], crop=True, nodata=0)
            
            # Get the maximum flood category within the buffer
            max_value = int(np.max(masked_data))
            
            # Return the maximum flood category if it's valid
            if max_value in self.flood_categories:
                return max_value
            else:
                return 0  # Default to no flood
                
        except Exception:
            return 0  # Default to no flood if there's an error
    
    def fetch_road_network(self):
        """Fetch road network from OpenStreetMap"""
        print("Fetching road network from OpenStreetMap...")
        try:
            # Get road network within the bounds - updated for OSMnx 2.0.3
            bbox = (self.west, self.south, self.east, self.north)
            self.road_network = ox.graph.graph_from_bbox(bbox, network_type='all')
            
            # Convert to GeoDataFrame
            nodes, edges = ox.graph_to_gdfs(self.road_network)
            self.road_gdf = edges.copy()
            
            # Keep only necessary columns
            if 'name' not in self.road_gdf.columns:
                self.road_gdf['name'] = 'Unnamed Road'
            if 'highway' not in self.road_gdf.columns:
                self.road_gdf['highway'] = 'road'
                
            self.road_gdf = self.road_gdf[['geometry', 'name', 'highway']].reset_index()
            
            print(f"Retrieved {len(self.road_gdf)} road segments")
            return self.road_gdf
            
        except Exception as e:
            print(f"Error fetching road network: {e}")
            # Create an empty GeoDataFrame as fallback
            self.road_gdf = gpd.GeoDataFrame(columns=['geometry', 'name', 'highway'])
            return self.road_gdf

    def fetch_infrastructure(self, infrastructure_types):
        """
        Fetch critical infrastructure from OpenStreetMap using definitions from JSON file.
        
        Parameters:
        -----------
        infrastructure_types : list
            List of infrastructure categories to fetch (e.g., ['Healthcare', 'Emergency Services'])
            
        Returns:
        --------
        GeoDataFrame
            GeoDataFrame containing the infrastructure
        """
        print(f"Fetching infrastructure categories: {', '.join(infrastructure_types)}...")
        
        all_pois = []
        
        for category in infrastructure_types:
            if category not in self.infrastructure_definitions:
                print(f"Warning: Category '{category}' not found in infrastructure definitions")
                continue
                
            print(f"\nProcessing {category}...")
            
            for item in self.infrastructure_definitions[category]:
                try:
                    # Create tags dict for the infrastructure type
                    tags = {item['type']: item['value']}
                    
                    # Fetch POIs
                    bbox = (self.west, self.south, self.east, self.north)
                    pois = ox.features.features_from_bbox(bbox, tags=tags)
                    
                    # Add infrastructure type if POIs were found
                    if not pois.empty:
                        # Handle NaN values and filter out problematic geometries
                        pois = pois.dropna(subset=['geometry'])
                        
                        # Keep only Point geometries to avoid issues
                        pois = pois[pois.geometry.type == 'Point']
                        
                        if not pois.empty:
                            pois['infrastructure_type'] = f"{category}_{item['value']}"
                            pois['description'] = item['description']
                            
                            # Keep only necessary columns
                            if 'name' in pois.columns:
                                # Replace NaN names with default
                                pois['name'] = pois['name'].fillna(f"Unnamed {item['value'].replace('_', ' ').title()}")
                                pois = pois[['geometry', 'name', 'infrastructure_type', 'description']]
                            else:
                                pois['name'] = f"Unnamed {item['value'].replace('_', ' ').title()}"
                                pois = pois[['geometry', 'name', 'infrastructure_type', 'description']]
                            
                            all_pois.append(pois)
                            print(f"  - Found {len(pois)} {item['value']} facilities")
                
                except Exception as e:
                    print(f"  - Error fetching {item['value']}: {e}")
        
        if all_pois:
            # Combine all POIs into a single GeoDataFrame
            self.infrastructure_gdf = gpd.GeoDataFrame(pd.concat(all_pois, ignore_index=True), crs="EPSG:4326")
            
            # Keep only Point geometries
            self.infrastructure_gdf = self.infrastructure_gdf[
                self.infrastructure_gdf.geometry.type == 'Point'
            ].reset_index(drop=True)
            
            print(f"\nRetrieved {len(self.infrastructure_gdf)} infrastructure points in total")
            return self.infrastructure_gdf
        else:
            # Create an empty GeoDataFrame as fallback
            self.infrastructure_gdf = gpd.GeoDataFrame(
                columns=['geometry', 'name', 'infrastructure_type', 'description'], 
                geometry='geometry',
                crs="EPSG:4326"
            )
            print("No infrastructure found")
            return self.infrastructure_gdf

    def assign_flood_categories(self):
        """Assign flood categories to roads and infrastructure"""
        print("Assigning flood categories to infrastructure...")
        
        # Assign flood categories to infrastructure
        if hasattr(self, 'infrastructure_gdf') and not self.infrastructure_gdf.empty:
            self.infrastructure_gdf['flood_category'] = self.infrastructure_gdf.geometry.apply(
                self.get_flood_category_at_point
            )
        
        print("Assigning flood categories to roads...")
        
        # Assign flood categories to roads
        if hasattr(self, 'road_gdf') and not self.road_gdf.empty:
            # Sample points along each road segment and get the maximum flood category
            def get_max_flood_for_line(line):
                # Sample points along the line (start, middle, end)
                if line.geom_type == 'LineString':
                    points = [
                        Point(line.coords[0]),
                        Point(line.interpolate(0.5, normalized=True)),
                        Point(line.coords[-1])
                    ]
                    
                    # Get flood category for each point
                    flood_categories = [self.get_flood_category_at_point(point) for point in points]
                    
                    # Return the maximum flood category
                    return max(flood_categories)
                else:
                    return 0
            
            # Apply the function to each road segment with a progress bar
            tqdm.pandas(desc="Processing road segments")
            self.road_gdf['flood_category'] = self.road_gdf.geometry.progress_apply(get_max_flood_for_line)

    def create_map(self, output_file="flood_impact_map.html"):
        """
        Create an interactive map showing flood impacts on infrastructure and roads.
        
        Parameters:
        -----------
        output_file : str
            Name of the output HTML file
        """
        print("Creating interactive map...")
        
        # Calculate the center of the map
        center_lat = (self.north + self.south) / 2
        center_lon = (self.east + self.west) / 2
        
        # Create a Folium map
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
        
        # # Add satellite basemap
        # folium.TileLayer(
        #     tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        #     attr='Google Satellite',
        #     name='Google Satellite',
        #     overlay=False,
        #     control=True
        # ).add_to(m)
        
        # Add a title to the map
        title_html = '''
             <h3 align="center" style="font-size:16px"><b>Flood Impact on Critical Infrastructure</b></h3>
             '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Draw bounding box
        bbox_coords = [
            [self.south, self.west],
            [self.south, self.east],
            [self.north, self.east],
            [self.north, self.west],
            [self.south, self.west]
        ]
        
        folium.Polygon(
            locations=[[lat, lon] for lat, lon in bbox_coords],
            color='black',
            weight=2,
            fill=False,
            popup='Analysis Area Boundary'
        ).add_to(m)
        
        # Add infrastructure to the map
        if hasattr(self, 'infrastructure_gdf') and not self.infrastructure_gdf.empty:
            # Create a marker cluster for infrastructure
            marker_cluster = MarkerCluster(name="Critical Infrastructure").add_to(m)
            
            # Add each infrastructure point to the map
            for idx, row in self.infrastructure_gdf.iterrows():
                # Get the flood category and color
                flood_cat = int(row['flood_category'])
                color = self.flood_colors.get(flood_cat, "#FFFFFF")
                
                # Create popup content
                popup_content = f"""
                <b>{row['name']}</b><br>
                Type: {row['infrastructure_type'].replace('_', ' ').title()}<br>
                Flood Category: {self.flood_categories.get(flood_cat, 'Unknown')}
                """
                
                # Add the marker to the cluster
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=folium.Popup(popup_content, max_width=300),
                    icon=folium.Icon(color='black', icon_color=color, icon='building', prefix='fa'),
                ).add_to(marker_cluster)
        
        # Add roads to the map
        if hasattr(self, 'road_gdf') and not self.road_gdf.empty:
            # Create a feature group for roads
            road_group = folium.FeatureGroup(name="Road Network").add_to(m)
            
            # Add each road segment to the map
            for idx, row in self.road_gdf.iterrows():
                # Get the flood category and color
                flood_cat = int(row['flood_category'])
                color = self.flood_colors.get(flood_cat, "#AAAAAA")
                
                # Skip roads with no flooding
                if flood_cat == 0:
                    continue
                
                # Create popup content
                road_name = row['name'] if isinstance(row['name'], str) else "Unnamed Road"
                popup_content = f"""
                <b>{road_name}</b><br>
                Type: {row['highway']}<br>
                Flood Category: {self.flood_categories.get(flood_cat, 'Unknown')}
                """
                
                # Add the road to the map
                folium.GeoJson(
                    row.geometry,
                    style_function=lambda x, color=color: {
                        'color': color,
                        'weight': 3,
                        'opacity': 0.8
                    },
                    popup=folium.Popup(popup_content, max_width=300)
                ).add_to(road_group)
        
        # Add a legend to the map
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 220px; height: 160px; 
                    border:2px solid grey; z-index:9999; font-size:14px;
                    background-color:white; padding: 10px;
                    border-radius: 6px;">
        <b>Flood Categories</b><br>
        '''
        
        for cat, desc in self.flood_categories.items():
            if cat > 0:  # Skip "No Flood" category
                color = self.flood_colors[cat]
                legend_html += f'<i style="background:{color}; width:15px; height:15px; display:inline-block; margin-right:5px;"></i>{desc}<br>'
        
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add flood overlay
        self.add_flood_overlay(m)
        
        # Save the map
        output_path = os.path.join(self.output_dir, output_file)
        m.save(output_path)
        print(f"Interactive map saved to {output_path}")
        
        return output_path
    
    def create_static_maps(self):
        """Create static maps for infrastructure and roads"""
        print("Creating static maps...")
        
        # Create directory for static maps
        static_maps_dir = os.path.join(self.output_dir, "static_maps")
        os.makedirs(static_maps_dir, exist_ok=True)
        
        # Define colors for plotting
        cmap = plt.cm.RdPu
        norm = plt.Normalize(vmin=0, vmax=4)
        
        # Create a map of infrastructure
        if hasattr(self, 'infrastructure_gdf') and not self.infrastructure_gdf.empty:
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Plot base map (flood extent)
            self.bounds_gdf.plot(ax=ax, color='lightgrey', alpha=0.5)
            
            # Plot infrastructure colored by flood category
            self.infrastructure_gdf.plot(
                ax=ax,
                column='flood_category',
                cmap=cmap,
                norm=norm,
                legend=True,
                markersize=50,
                categorical=True,
                legend_kwds={'title': 'Flood Category'},
                zorder=10,
            )
            
            # Set title and labels
            plt.title('Flood Impact on Critical Infrastructure')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            
            # Save the figure
            infra_map_path = os.path.join(static_maps_dir, 'infrastructure_flood_impact.png')
            plt.savefig(infra_map_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Infrastructure map saved to {infra_map_path}")
        
        # Create a map of roads
        if hasattr(self, 'road_gdf') and not self.road_gdf.empty:
            fig, ax = plt.subplots(figsize=(12, 10))
            
            # Plot base map (flood extent)
            self.bounds_gdf.plot(ax=ax, color='lightgrey', alpha=0.5)
            
            # Plot roads colored by flood category
            self.road_gdf.plot(
                ax=ax,
                column='flood_category',
                cmap=cmap,
                norm=norm,
                legend=True,
                linewidth=1.5,
                categorical=True,
                legend_kwds={'title': 'Flood Category'},
                zorder=2,
            )
            
            # Set title and labels
            plt.title('Flood Impact on Road Network')
            plt.xlabel('Longitude')
            plt.ylabel('Latitude')
            
            # Save the figure
            road_map_path = os.path.join(static_maps_dir, 'road_flood_impact.png')
            plt.savefig(road_map_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Road network map saved to {road_map_path}")
    
    def export_data(self):
        """Export the processed data to GeoJSON files"""
        print("Exporting data to GeoJSON...")
        
        # Create directory for data exports
        export_dir = os.path.join(self.output_dir, "data")
        os.makedirs(export_dir, exist_ok=True)
        
        # Export infrastructure data
        if hasattr(self, 'infrastructure_gdf') and not self.infrastructure_gdf.empty:
            infra_path = os.path.join(export_dir, 'infrastructure_flood_impact.geojson')
            self.infrastructure_gdf.to_file(infra_path, driver='GeoJSON')
            print(f"Infrastructure data exported to {infra_path}")
        
        # Export road network data
        if hasattr(self, 'road_gdf') and not self.road_gdf.empty:
            road_path = os.path.join(export_dir, 'road_flood_impact.geojson')
            self.road_gdf.to_file(road_path, driver='GeoJSON')
            print(f"Road network data exported to {road_path}")
    
    def run(self, infrastructure_types, scientific_map_file=None):
        """
        Run the full flood impact mapping process.
        
        Parameters:
        -----------
        infrastructure_types : list
            List of infrastructure types to analyze
        scientific_map_file : str, optional
            Path to save the scientific map. If None, will use default name.
        """
        # Fetch data from OpenStreetMap
        self.fetch_road_network()
        self.fetch_infrastructure(infrastructure_types)
        
        # Assign flood categories
        self.assign_flood_categories()
        
        # Create maps and export data
        self.create_map()
        self.create_static_maps()
        self.export_data()
        
        # Create scientific publication-quality map
        self.create_scientific_map(scientific_map_file)
        
        print("Flood impact mapping completed successfully!")

    def add_flood_overlay(self, m):
        """
        Add a flood map overlay to the interactive map.
        
        Parameters:
        -----------
        m : folium.Map
            The map to add the overlay to
        """
        # Create a temporary colormap image of the flood data
        temp_dir = os.path.join(self.output_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Define colors for flood categories
        colors = [
            (255, 255, 255, 0),    # No flood (transparent)
            (255, 200, 200, 128),   # Nuisance flood (light red, semi-transparent)
            (255, 128, 128, 160),   # Minor flood (medium red, semi-transparent)
            (255, 0, 0, 192),       # Moderate flood (dark red, semi-transparent)
            (128, 0, 128, 224)      # Major flood (purple, semi-transparent)
        ]
        
        try:
            # Create a colored image from the flood data
            height, width = self.flood_data.shape
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            
            # Apply colors based on flood categories
            for cat in range(5):  # 0 to 4
                mask = (self.flood_data == cat)
                rgba[mask] = colors[cat]
            
            # Create and save the image
            img = Image.fromarray(rgba)
            img_path = os.path.join(temp_dir, 'flood_overlay.png')
            img.save(img_path)
            
            # Get the bounds for the image overlay
            bounds = [
                [self.south, self.west],
                [self.north, self.east]
            ]
            
            # Add the image overlay to the map
            folium.raster_layers.ImageOverlay(
                image=img_path,
                bounds=bounds,
                opacity=0.7,
                name="Flood Map"
            ).add_to(m)
            
        except Exception as e:
            print(f"Error creating flood overlay: {e}")
            
        return m

    def create_scientific_map(self, output_file=None):
        """
        Create a publication-quality scientific map with coordinates, no basemap labels,
        and proper markers for infrastructure.
        
        Parameters:
        -----------
        output_file : str
            Path to save the output map. If None, will use 'scientific_flood_map.png' in output directory.
            
        Returns:
        --------
        str
            Path to the saved map file
        """
        print("Creating scientific publication-quality map...")
        
        if output_file is None:
            output_file = os.path.join(self.output_dir, 'scientific_flood_map.png')
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Set up the plot with coordinates
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        
        # Plot the boundary of the study area
        bounds_wgs84 = self.bounds_gdf.to_crs(epsg=4326)
        bounds_wgs84.boundary.plot(ax=ax, color='black', linewidth=2)
        
        # Define marker styles for different infrastructure categories
        category_markers = {
            'Healthcare': {'marker': 'H', 'markersize': 100, 'edgecolor': 'black'},
            'Emergency Services': {'marker': '^', 'markersize': 80, 'edgecolor': 'black'},
            'Shelter and Facilities': {'marker': 's', 'markersize': 80, 'edgecolor': 'black'},
            'Transportation': {'marker': 'o', 'markersize': 70, 'edgecolor': 'black'},
            'Utilities': {'marker': '*', 'markersize': 80, 'edgecolor': 'black'}
        }
        
        # Plot roads with flood impacts
        if hasattr(self, 'road_gdf') and not self.road_gdf.empty:
            # Plot all roads first in gray
            self.road_gdf.plot(
                ax=ax,
                color=self.flood_colors[0],  # Gray for no flood
                linewidth=1.5,
                zorder=1
            )
            
            # Then plot flooded roads by category
            flooded_roads = self.road_gdf[self.road_gdf.flood_category > 0]
            if not flooded_roads.empty:
                for cat in range(1, 5):
                    cat_roads = flooded_roads[flooded_roads.flood_category == cat]
                    if not cat_roads.empty:
                        color = self.flood_colors[cat]
                        cat_roads.plot(
                            ax=ax,
                            color=color,
                            linewidth=1.5,
                            zorder=2
                        )
        
        # Plot infrastructure with proper markers
        if hasattr(self, 'infrastructure_gdf') and not self.infrastructure_gdf.empty:
            # Group by infrastructure category
            for category in self.infrastructure_definitions.keys():
                # Get the base marker style for this category
                base_style = category_markers.get(category, {'marker': 'o', 'markersize': 60, 'edgecolor': 'black'})
                
                # Get all infrastructure points for this category
                category_points = self.infrastructure_gdf[
                    self.infrastructure_gdf.infrastructure_type.str.startswith(category)
                ]
                
                if not category_points.empty:
                    # Plot all points for this category with the same marker
                    category_points.plot(
                        ax=ax,
                        color=self.flood_colors[0],  # Gray for no flood
                        **base_style,
                        label=category,
                        zorder=3
                    )
                    
                    # Now plot each flood category with different colors
                    for cat in range(1, 5):  # Start from 1 to skip no flood
                        cat_points = category_points[category_points.flood_category == cat]
                        if not cat_points.empty:
                            color = self.flood_colors[cat]
                            cat_points.plot(
                                ax=ax,
                                color=color,
                                **base_style,
                                zorder=4
                            )
        
        # Add gridlines
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Create two separate legends
        # First legend for infrastructure categories
        handles1, labels1 = [], []
        for category in self.infrastructure_definitions.keys():
            style = category_markers.get(category, {'marker': 'o', 'markersize': 60})
            handles1.append(plt.Line2D([0], [0], marker=style['marker'], color='black',
                                     markersize=style['markersize']/10, linestyle='None'))
            labels1.append(category)
        
        # Second legend for flood categories
        handles2, labels2 = [], []
        for cat in range(5):  # Include category 0 (no flood)
            color = self.flood_colors[cat]
            handles2.append(plt.Rectangle((0, 0), 1, 1, color=color))
            labels2.append(self.flood_categories[cat])
        
        # Add the legends
        legend1 = ax.legend(handles1, labels1, 
                          loc='upper right',
                          frameon=False,
                          framealpha=0.9,
                          ncol=5)
        
        # Add the first legend to the axes
        ax.add_artist(legend1)
        
        # Add the second legend
        ax.legend(handles2, labels2,
                 loc='lower right',
                 frameon=False,
                 framealpha=0.9,
                 ncol=5)
        
        # Adjust layout and save
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Scientific map saved to {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Map flood impacts on critical infrastructure and road networks')
    
    parser.add_argument('flood_map', type=str, help='Path to the GeoTIFF flood map')
    parser.add_argument('--output-dir', type=str, default='output', help='Directory to save output files')
    parser.add_argument('--search-distance', type=float, default=1e-5, help='Distance in meters to search for flood values')
    parser.add_argument('--infrastructure', type=str, nargs='+', 
                        default=['hospital', 'school', 'fire_station', 'police', 'grocery', 'pharmacy', 'fuel'],
                        help='Types of infrastructure to analyze')
    parser.add_argument('--scientific-map', type=str, help='Filename for the scientific publication-quality map')
    
    args = parser.parse_args()
    
    # Create and run the flood impact mapper
    mapper = FloodImpactMapper(
        flood_map_path=args.flood_map,
        output_dir=args.output_dir,
        search_distance=args.search_distance
    )
    
    mapper.run(args.infrastructure, args.scientific_map)


if __name__ == '__main__':
    import pandas as pd
    main() 