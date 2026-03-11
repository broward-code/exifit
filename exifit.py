import streamlit as st
import piexif
from PIL import Image
import io
import folium
from streamlit_folium import st_folium

# --- 1. SESSION STATE MANAGEMENT ---
if 'lat' not in st.session_state:
    st.session_state.lat = 0.0
if 'lon' not in st.session_state:
    st.session_state.lon = 0.0
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.lat = 0.0
    st.session_state.lon = 0.0
    st.session_state.uploader_key += 1

# --- 2. CONVERSION UTILITIES ---
def dms_to_decimal(degrees, minutes, seconds, direction):
    decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
    if direction in ['S', 'W']:
        decimal = -decimal
    return decimal

def decimal_to_dms(decimal):
    abs_dec = abs(decimal)
    d = int(abs_dec)
    m = int((abs_dec - d) * 60)
    s = (abs_dec - d - m/60) * 3600
    return d, m, round(s, 3)

def decimal_to_exif_rational(val):
    d, m, s = decimal_to_dms(val)
    return ((d, 1), (m, 1), (int(round(s * 1000)), 1000))

def parse_exif_gps(gps_data):
    def to_float(num_tuple):
        return num_tuple[0] / num_tuple[1]
    try:
        lat = to_float(gps_data[2][0]) + to_float(gps_data[2][1])/60 + to_float(gps_data[2][2])/3600
        if gps_data[1].decode() == 'S': lat = -lat
        lon = to_float(gps_data[4][0]) + to_float(gps_data[4][1])/60 + to_float(gps_data[4][2])/3600
        if gps_data[3].decode() == 'W': lon = -lon
        return lat, lon
    except: return 0.0, 0.0

# --- 3. APP UI ---
st.set_page_config(layout="wide", page_title="Chisheu Precision EXIF")

with st.sidebar:
    st.title("⚙️ App Controls")
    st.button("🔄 Reset / New Photo", on_click=reset_app, use_container_width=True)
    st.divider()
    st.write(f"**Current Lat:** `{st.session_state.lat:.6f}`")
    st.write(f"**Current Lon:** `{st.session_state.lon:.6f}`")

st.title("📍 Precision Geotagging Tool")

uploaded_file = st.file_uploader("Upload JPEG", type=["jpg", "jpeg"], key=f"up_{st.session_state.uploader_key}")

if uploaded_file:
    img = Image.open(uploaded_file)
    
    # Initialize from file
    if st.session_state.lat == 0.0 and st.session_state.lon == 0.0:
        exif_dict = piexif.load(img.info.get('exif', b''))
        st.session_state.lat, st.session_state.lon = parse_exif_gps(exif_dict.get("GPS", {}))

    # SWAPPED PANES: Map on Left, Photo/Controls on Right
    col_map, col_info = st.columns([1.5, 1])

    with col_map:
        st.subheader("Interactive Map Fine-Tuning")
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16)
        
        # Draggable Marker
        folium.Marker(
            [st.session_state.lat, st.session_state.lon],
            draggable=True,
            tooltip="Drag to fine-tune",
            icon=folium.Icon(color='red', icon='screenshot', prefix='fa')
        ).add_to(m)
        
        # Capture Map Events
        map_data = st_folium(m, height=550, width=None, key="main_map")

        # REAL-TIME UPDATE: If pin is moved, update session state
        if map_data and map_data.get("last_object_clicked"):
            new_lat = map_data["last_object_clicked"]["lat"]
            new_lon = map_data["last_object_clicked"]["lng"]
            if round(new_lat, 6) != round(st.session_state.lat, 6):
                st.session_state.lat = new_lat
                st.session_state.lon = new_lon
                st.rerun()

    with col_info:
        st.image(img, use_container_width=True, caption="Source Image Preview")
        
        st.divider()
        st.subheader("Coordinate Entry")
        mode = st.radio("Entry Format", ["Decimal", "DMS"], horizontal=True)

        if mode == "Decimal":
            new_lat_input = st.number_input("Latitude", value=st.session_state.lat, format="%.6f")
            new_lon_input = st.number_input("Longitude", value=st.session_state.lon, format="%.6f")
            
            if new_lat_input != st.session_state.lat or new_lon_input != st.session_state.lon:
                st.session_state.lat = new_lat_input
                st.session_state.lon = new_lon_input
                st.rerun()
        
        else:
            d_lat, m_lat, s_lat = decimal_to_dms(st.session_state.lat)
            d_lon, m_lon, s_lon = decimal_to_dms(st.session_state.lon)
            
            st.write("**Latitude (DMS)**")
            r1c1, r1c2, r1c3, r1c4 = st.columns([1, 1, 1, 1.2])
            lat_dir = r1c1.selectbox("Dir", ["N", "S"], index=0 if st.session_state.lat >= 0 else 1, key="ldir")
            lat_d = r1c2.number_input("Deg", value=d_lat, key="ld")
            lat_m = r1c3.number_input("Min", value=m_lat, key="lm")
            lat_s = r1c4.number_input("Sec", value=s_lat, format="%.3f", key="ls")
            
            st.write("**Longitude (DMS)**")
            r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1, 1, 1.2])
            lon_dir = r2c1.selectbox("Dir", ["E", "W"], index=0 if st.session_state.lon >= 0 else 1, key="odir")
            lon_d = r2c2.number_input("Deg", value=d_lon, key="od")
            lon_m = r2c3.number_input("Min", value=m_lon, key="om")
            lon_s = r2c4.number_input("Sec", value=s_lon, format="%.3f", key="os")

            # Convert DMS back to decimal to check for manual changes
            calc_lat = dms_to_decimal(lat_d, lat_m, lat_s, lat_dir)
            calc_lon = dms_to_decimal(lon_d, lon_m, lon_s, lon_dir)
            
            if round(calc_lat, 6) != round(st.session_state.lat, 6) or round(calc_lon, 6) != round(st.session_state.lon, 6):
                st.session_state.lat = calc_lat
                st.session_state.lon = calc_lon
                st.rerun()

        if st.button("💾 Apply & Download", type="primary", use_container_width=True):
            exif_dict = piexif.load(img.info.get('exif', b''))
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: 'N' if st.session_state.lat >= 0 else 'S',
                piexif.GPSIFD.GPSLatitude: decimal_to_exif_rational(st.session_state.lat),
                piexif.GPSIFD.GPSLongitudeRef: 'E' if st.session_state.lon >= 0 else 'W',
                piexif.GPSIFD.GPSLongitude: decimal_to_exif_rational(st.session_state.lon),
            }
            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif_bytes)
            st.download_button("Download Modified Image", buf.getvalue(), f"fixed_{uploaded_file.name}", "image/jpeg")
