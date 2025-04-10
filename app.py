import streamlit as st
from PIL import Image, ExifTags
import xml.etree.ElementTree as ET
import leafmap
import leafmap.foliumap as leafmap
import folium
import pandas as pd
from PIL import Image
import io
import base64
import tempfile
import shapefile
from io import BytesIO
import zipfile
import geopandas as gpd
from shapely.geometry import LineString
import os
import math
from fractions import Fraction

def convert_to_decimal_coords(degrees, minutes, seconds, direction):
    """Convert GPS coordinates to decimal format"""
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal

def organize_exif_info(exif_data, gps_info):
    """Organizes EXIF and GPS data into logical groups"""
    groups = {
        'Basic Info': {
            'icon': '📷',
            'items': {}
        },
        'Camera Settings': {
            'icon': '⚙️',
            'items': {}
        },
        'GPS Information': {
            'icon': '📍',
            'items': {}
        },
        'Image Details': {
            'icon': '🖼️',
            'items': {}
        },
        'Other': {
            'icon': '📌',
            'items': {}
        }
    }
    
    # Basic Info mapping
    basic_info_tags = ['Make', 'Model', 'Software', 'DateTime', 'DateTimeOriginal']
    camera_settings_tags = ['ExposureTime', 'FNumber', 'ISOSpeedRatings', 'FocalLength', 
                          'ExposureMode', 'WhiteBalance', 'MeteringMode']
    image_details_tags = ['ImageWidth', 'ImageLength', 'XResolution', 'YResolution', 
                         'Orientation', 'ColorSpace']
    
    # Process EXIF data
    if exif_data:
        for tag, value in exif_data.items():
            if tag == 'GPSInfo':  # Skip GPSInfo as we handle it separately
                continue
                
            if tag in basic_info_tags:
                groups['Basic Info']['items'][tag] = value
            elif tag in camera_settings_tags:
                groups['Camera Settings']['items'][tag] = value
            elif tag in image_details_tags:
                groups['Image Details']['items'][tag] = value
            else:
                groups['Other']['items'][tag] = value
    
    # Process GPS data
    if gps_info and isinstance(gps_info, dict):
        for key, value in gps_info.items():
            if key in ['decimal_latitude', 'decimal_longitude']:
                formatted_value = f"{value:.6f}"
            else:
                formatted_value = value
            groups['GPS Information']['items'][key] = formatted_value
    
    # Remove empty groups
    return {k: v for k, v in groups.items() if v['items']}

def format_exif_value(value):
    """Format EXIF values for display"""
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except:
            return str(value)
    elif isinstance(value, (tuple, list)):
        return ', '.join(str(x) for x in value)
    elif isinstance(value, dict):
        return ', '.join(f"{k}: {v}" for k, v in value.items())
    elif isinstance(value, Fraction):
        return float(value)
    return str(value)

def format_exif_key(key):
    """Format EXIF keys for display"""
    # Add spaces before capital letters
    formatted = ''.join(' ' + c if c.isupper() else c for c in str(key)).strip()
    # Handle special cases
    formatted = formatted.replace('G P S', 'GPS')
    formatted = formatted.replace('I S O', 'ISO')
    formatted = formatted.replace('F Number', 'F-Number')
    return formatted

def main():
    st.markdown('')

    st.markdown(
        '<span style="font-size: 24px;">Photo Geotag Extraction</span>',
        help="This application serves as a powerful tool for extracting and visualizing geotag information embedded within JPG images...",
        unsafe_allow_html=True
    )

    uploaded_files = st.file_uploader("**Choose JPG file (s)**", type="jpg", accept_multiple_files=True)

    # Initialize session state
    if 'data' not in st.session_state:
        st.session_state['data'] = []
        st.session_state['geotagged_photos'] = []
        st.session_state['kml_content'] = None
        st.session_state['shapefile_content'] = None

    with st.expander("Settings"):
        # Create a row with three columns for sliders
        slider_col1, slider_col2, slider_col3 = st.columns(3)

        # Slider to adjust thumbnail size for photo view
        with slider_col1:
            thumbnail_size_photo = st.slider('Adjust the Thumbnail Size for Photos Inspection View', min_value=150,
                                             max_value=1000, value=500, step=10)

        # Slider to adjust thumbnail size for map view
        with slider_col2:
            thumbnail_size_map = st.slider('Adjust the Thumbnail Size for Map View', min_value=100, max_value=300,
                                           value=200, step=10)

        # Slider to adjust line length for direction lines
        with slider_col3:
            line_length = st.slider('Adjust Direction Line Length (m)', min_value=10, max_value=500,
                                    value=50, step=10)

    # Create a row with three columns
    col1, col2, col3 = st.columns([2, 1, 1])

    # Place the "Process Images" button in the first column
    process_images_button = col1.button('Process Photos')

    if process_images_button:
        if uploaded_files:
            # Process images and store the data in the session state
            st.session_state['data'] = process_images(uploaded_files, thumbnail_size_photo)
            st.session_state['geotagged_photos'] = [d for d in st.session_state['data'] if d.get("gps") != "Missing Geotag"]

            if any('gps' in photo and photo['gps'] != "Missing Geotag" for photo in st.session_state['data']):
                # Create a DataFrame and display it
                df = pd.DataFrame(st.session_state['data'])
                df['gps'] = df['gps'].apply(lambda x: format_geotags(x) if x != "Missing Geotag" else x)
                df.index = [""] * len(df)  # remove row indices

    tab1, tab2 = st.tabs(["Photo Inspection View", "Map View"])

    with tab1:
        if process_images_button and uploaded_files:
            if st.session_state['data']:
                for photo_data in st.session_state['data']:
                    with st.expander(f"📷 {photo_data['name']}", expanded=False):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.image(photo_data['thumbnail'])
                        
                        with col2:
                            # Organize and display EXIF data in groups
                            organized_info = organize_exif_info(photo_data['exif'], photo_data['gps'])
                            
                            for group_name, group_data in organized_info.items():
                                st.markdown(f"### {group_data['icon']} {group_name}")
                                
                                # Create a clean two-column layout for details
                                for key, value in group_data['items'].items():
                                    formatted_key = format_exif_key(key)
                                    formatted_value = format_exif_value(value)
                                    
                                    cols = st.columns([1, 2])
                                    with cols[0]:
                                        st.markdown(f"**{formatted_key}:**")
                                    with cols[1]:
                                        st.write(formatted_value)
                                    
                                st.markdown("---")

    with tab2:
        if process_images_button and uploaded_files:
            if st.session_state['geotagged_photos']:
                # Create KML content
                kml_content = create_kml(st.session_state['geotagged_photos'], line_length=line_length)
                st.session_state['kml_content'] = kml_content.encode('utf-8') if isinstance(kml_content, str) else kml_content

                # Create Shapefile content
                shapefile_content = create_shapefile(st.session_state['geotagged_photos'], line_length=line_length)
                st.session_state['shapefile_content'] = shapefile_content

                # Initialize or update the map
                if 'map' not in st.session_state or process_images_button:
                    m = leafmap.Map(center=[-33.0333135,146.4933441], zoom=10)

                    # Add markers for geotagged photos
                    for item in st.session_state['geotagged_photos']:
                        gps_data = item['gps']
                        if isinstance(gps_data, dict) and 'decimal_latitude' in gps_data and 'decimal_longitude' in gps_data:
                            lat = gps_data['decimal_latitude']
                            lon = gps_data['decimal_longitude']
                            label = item['name']

                            content = f"""
                            <div style="text-align: center;">
                                <img src="{item['thumbnail']}" alt="{label}" width="{thumbnail_size_map}px" style="border: 1px solid #ccc;"><br>
                                <b>{label}</b><hr style="margin: 2px 0;">
                                <div style="text-align: left;">
                                    Lat: {round(lat, 5)}<br>
                                    Lon: {round(lon, 5)}
                                </div>
                            </div>
                            """

                            m.add_marker(location=[lat, lon], popup=content)
                            # Add direction lines
                            add_photo_direction_lines(m, st.session_state['geotagged_photos'], distance=line_length)

                    # Check if any markers have been added and zoom to their extent
                    bounds = calculate_map_bounds(st.session_state['geotagged_photos'])
                    if bounds:
                        min_lat, min_lon, max_lat, max_lon = bounds
                        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
                    else:
                        st.warning(
                            "Could not retrieve the map bounds. Please make sure the geotagged photos have valid coordinates.")
                    m.add_basemap('HYBRID')

                    # Save the map in the session state
                    st.session_state['map'] = m

                # Create download links for KML and Shapefile
                download_links = ""
                if st.session_state['kml_content']:
                    kml_b64 = base64.b64encode(st.session_state['kml_content']).decode('utf-8')
                    kml_link = f"<a href='data:application/vnd.google-earth.kml+xml;base64,{kml_b64}' download='Photo_Locations.kml' style='text-decoration: none; color: #1f77b4;'>Download KML</a>"
                    download_links += kml_link

                if st.session_state['shapefile_content']:
                    shapefile_b64 = base64.b64encode(st.session_state['shapefile_content']).decode('utf-8')
                    shapefile_link = f"<a href='data:application/zip;base64,{shapefile_b64}' download='Photo_Locations.zip' style='text-decoration: none; color: #1f77b4;'>Download Shapefile</a>"
                    download_links += " | " + shapefile_link if download_links else shapefile_link

                # Place download links at top right corner of map
                if download_links:
                    download_html = f"""
                    <div style="position: relative;">
                        <div style="position: absolute; top: 0; right: 0; z-index: 999;">
                            {download_links}
                        </div>
                    </div>
                    """
                    st.components.v1.html(download_html, height=30)
                    st.session_state['map'].to_streamlit(height=570)
            else:
                st.warning("No geotagged photos found. The map cannot be displayed.")
        else:
            st.warning("Please upload at least one photo or reprocess.")

# Copy all the helper functions from geotag_photo_analyser.py
def calculate_destination(lat, lon, bearing, distance):
    """Calculate destination point given start point, bearing, and distance."""
    R = 6371e3  # Earth radius in meters
    bearing = math.radians(bearing)

    lat = math.radians(lat)
    lon = math.radians(lon)

    lat2 = math.asin(math.sin(lat) * math.cos(distance / R) +
                     math.cos(lat) * math.sin(distance / R) * math.cos(bearing))
    lon2 = lon + math.atan2(math.sin(bearing) * math.sin(distance / R) * math.cos(lat),
                            math.cos(distance / R) - math.sin(lat) * math.sin(lat2))

    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return lat2, lon2

def process_images(uploaded_files, thumbnail_size):
    """Process uploaded images to extract EXIF and create thumbnails"""
    all_data = []
    for uploaded_file in uploaded_files:
        try:
            with Image.open(uploaded_file) as img:
                # Get EXIF data
                exif_data = {}
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    for tag_id, value in img._getexif().items():
                        tag = ExifTags.TAGS.get(tag_id, tag_id)
                        exif_data[tag] = value
                
                # Extract GPS data
                gps_info = extract_geotags(exif_data)
                
                # Create thumbnail
                thumbnail = create_thumbnail(img, thumbnail_size)
                
                data = {
                    "name": uploaded_file.name,
                    "exif": exif_data,
                    "gps": gps_info,
                    "thumbnail": thumbnail
                }
                all_data.append(data)
                
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
            continue
            
    return all_data

def get_exif_data(img):
    exif_data = {}
    if hasattr(img, '_getexif') and img._getexif() is not None:
        for tag_id, value in img._getexif().items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif_data[tag] = value
    return exif_data

def extract_geotags(exif_data):
    """Extract GPS information from EXIF data"""
    if not exif_data or 'GPSInfo' not in exif_data:
        return "Missing Geotag"

    gps_info = {}
    try:
        gps_data = exif_data['GPSInfo']
        
        # Extract latitude
        if all(k in gps_data for k in [1, 2, 3, 4]):  # 1=Latitude, 2=Latitude Ref, 3=Longitude, 4=Longitude Ref
            lat = gps_data[2]
            lat_ref = gps_data[1]
            lon = gps_data[4]
            lon_ref = gps_data[3]
            
            if isinstance(lat, tuple) and isinstance(lon, tuple):
                lat_dec = convert_to_decimal_coords(lat[0], lat[1], lat[2], lat_ref)
                lon_dec = convert_to_decimal_coords(lon[0], lon[1], lon[2], lon_ref)
                
                gps_info['decimal_latitude'] = lat_dec
                gps_info['decimal_longitude'] = lon_dec
                gps_info['latitude'] = lat
                gps_info['longitude'] = lon
                gps_info['latitude_ref'] = lat_ref
                gps_info['longitude_ref'] = lon_ref
        
        # Extract altitude if available
        if 6 in gps_data:  # 6 = Altitude
            altitude = float(gps_data[6])
            if 5 in gps_data and gps_data[5] == 1:  # 5 = Altitude ref (0 = above sea level)
                altitude = -altitude
            gps_info['altitude'] = altitude
        
        # Extract direction if available
        if 17 in gps_data:  # 17 = Image Direction
            direction = float(gps_data[17])
            gps_info['GPSImgDirection'] = direction
            
        return gps_info
    except Exception as e:
        st.error(f"Error extracting GPS data: {str(e)}")
        return "Missing Geotag"

def parse_geotag(geotag):
    # Custom parsing logic for geotag
    return geotag

def create_thumbnail(img, size):
    img.thumbnail((size, size))
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f'data:image/jpeg;base64,{img_str}'

def format_geotags(geotags):
    # Custom formatting logic for displaying geotags
    return geotags

def create_kml(photos, line_length=50):
    """Create KML file content from photo data."""
    kml = ET.Element('kml')
    kml.set('xmlns', 'http://www.opengis.net/kml/2.2')
    doc = ET.SubElement(kml, 'Document')

    # Create styles
    # Style for points
    style_point = ET.SubElement(doc, 'Style', id='photoStyle')
    icon_style = ET.SubElement(style_point, 'IconStyle')
    icon = ET.SubElement(icon_style, 'Icon')
    href = ET.SubElement(icon, 'href')
    href.text = 'http://maps.google.com/mapfiles/kml/pushpin/blue-pushpin.png'

    # Style for lines
    style_line = ET.SubElement(doc, 'Style', id='directionStyle')
    line_style = ET.SubElement(style_line, 'LineStyle')
    color = ET.SubElement(line_style, 'color')
    color.text = 'ff0000ff'  # Blue color
    width = ET.SubElement(line_style, 'width')
    width.text = '2'

    for photo in photos:
        gps_data = photo['gps']
        if isinstance(gps_data, dict) and 'decimal_latitude' in gps_data and 'decimal_longitude' in gps_data:
            lat = gps_data['decimal_latitude']
            lon = gps_data['decimal_longitude']

            # Create marker placemark
            marker_placemark = ET.SubElement(doc, 'Placemark')
            name = ET.SubElement(marker_placemark, 'name')
            name.text = photo['name']
            
            description = ET.SubElement(marker_placemark, 'description')
            description.text = f"Photo taken at: {lat}, {lon}"
            
            style_url = ET.SubElement(marker_placemark, 'styleUrl')
            style_url.text = '#photoStyle'
            
            point = ET.SubElement(marker_placemark, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{lon},{lat},0"

            # Create direction line placemark if direction is available
            if 'GPSImgDirection' in gps_data:
                bearing = float(gps_data['GPSImgDirection'])
                dest_lat, dest_lon = calculate_destination(lat, lon, bearing, line_length)
                
                line_placemark = ET.SubElement(doc, 'Placemark')
                line_name = ET.SubElement(line_placemark, 'name')
                line_name.text = f"{photo['name']} - Direction"
                
                line_desc = ET.SubElement(line_placemark, 'description')
                line_desc.text = f"Direction: {bearing}°"
                
                line_style_url = ET.SubElement(line_placemark, 'styleUrl')
                line_style_url.text = '#directionStyle'
                
                line_string = ET.SubElement(line_placemark, 'LineString')
                line_coords = ET.SubElement(line_string, 'coordinates')
                line_coords.text = f"{lon},{lat},0 {dest_lon},{dest_lat},0"

    return ET.tostring(kml, encoding='utf-8', xml_declaration=True)

def create_shapefile(photos, line_length=50):
    """Create Shapefile content from photo data."""
    tmpdir = tempfile.mkdtemp()
    try:
        # Base paths for point and line shapefiles
        point_base = os.path.join(tmpdir, "photos")
        line_base = os.path.join(tmpdir, "photo_directions")

        # Create point shapefile
        w = shapefile.Writer(point_base)
        w.shapeType = shapefile.POINT

        # Define fields
        w.field("Name", "C", 50)
        w.field("Latitude", "N", 20, 10)
        w.field("Longitude", "N", 20, 10)
        w.field("Direction", "N", 20, 10)

        # Add points
        for photo in photos:
            gps_data = photo['gps']
            if isinstance(gps_data, dict) and 'decimal_latitude' in gps_data and 'decimal_longitude' in gps_data:
                lat = gps_data['decimal_latitude']
                lon = gps_data['decimal_longitude']
                direction = gps_data.get('GPSImgDirection', 0)
                
                w.point(lon, lat)  # Shapefile expects (lon, lat)
                w.record(photo['name'], lat, lon, direction)

        w.close()

        # Create line shapefile if we have direction data
        if any('GPSImgDirection' in photo.get('gps', {}) for photo in photos):
            w_line = shapefile.Writer(line_base)
            w_line.shapeType = shapefile.POLYLINE

            # Define fields for lines
            w_line.field("Name", "C", 50)
            w_line.field("Direction", "N", 20, 10)

            # Add direction lines
            for photo in photos:
                gps_data = photo['gps']
                if isinstance(gps_data, dict):
                    if all(key in gps_data for key in ['GPSImgDirection', 'decimal_latitude', 'decimal_longitude']):
                        lat = gps_data['decimal_latitude']
                        lon = gps_data['decimal_longitude']
                        bearing = float(gps_data['GPSImgDirection'])
                        dest_lat, dest_lon = calculate_destination(lat, lon, bearing, line_length)

                        # Create line - shapefile expects list of [lon, lat] pairs
                        w_line.line([[[lon, lat], [dest_lon, dest_lat]]])
                        w_line.record(photo['name'], bearing)

            w_line.close()

        # Create projection files
        prj_content = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
        
        # Write PRJ file for points
        with open(point_base + '.prj', 'w') as prj:
            prj.write(prj_content)
        
        # Write PRJ file for lines if they exist
        if os.path.exists(line_base + '.shp'):
            with open(line_base + '.prj', 'w') as prj:
                prj.write(prj_content)

        # Create ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add point shapefile components
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                if os.path.exists(point_base + ext):
                    zipf.write(point_base + ext, f"photos{ext}")

            # Add line shapefile components if they exist
            if os.path.exists(line_base + '.shp'):
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    if os.path.exists(line_base + ext):
                        zipf.write(line_base + ext, f"photo_directions{ext}")

        # Get the zip content
        zip_buffer.seek(0)
        content = zip_buffer.getvalue()
        zip_buffer.close()
        return content

    finally:
        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            st.error(f"Error cleaning up temporary files: {str(e)}")
            return None

def add_photo_direction_lines(m, photos, distance=50):
    """Add direction lines to the map for the given photos."""
    for photo in photos:
        gps_data = photo['gps']
        if isinstance(gps_data, dict):
            if 'GPSImgDirection' in gps_data and 'decimal_latitude' in gps_data and 'decimal_longitude' in gps_data:
                lat = gps_data['decimal_latitude']
                lon = gps_data['decimal_longitude']
                bearing = float(gps_data['GPSImgDirection'])
                dest_lat, dest_lon = calculate_destination(lat, lon, bearing, distance)
                
                # Create line using folium.PolyLine
                line = folium.PolyLine(
                    locations=[[lat, lon], [dest_lat, dest_lon]],
                    weight=2,
                    color='blue',
                    opacity=0.8
                )
                line.add_to(m)

def calculate_map_bounds(photos):
    """Calculate the bounds of the map based on the given photos."""
    lats = []
    lons = []
    for photo in photos:
        gps_data = photo['gps']
        if isinstance(gps_data, dict):
            if 'decimal_latitude' in gps_data and 'decimal_longitude' in gps_data:
                lats.append(gps_data['decimal_latitude'])
                lons.append(gps_data['decimal_longitude'])
    if lats and lons:
        return min(lats), min(lons), max(lats), max(lons)
    return None

if __name__ == "__main__":
    main()
