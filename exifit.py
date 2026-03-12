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
    # 1000 denominator preserves 3 decimal places for seconds in the metadata hex
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
    except: 
        return 0.0, 0.0

# --- 3. APP UI ---
st.set_page_config(layout="wide", page_title="Chisheu Precision Geotag")

# Sidebar for feedback and reset
with st.sidebar:
    st.title("⚙️ Controls")
    st.button("🔄 Reset / New Photo", on_click=reset_app, use_container_width=True)
    st.divider()
    st.metric("Latitude", f"{st.session_state.lat:.6f}")
    st.metric("Longitude", f"{st.session_state.lon:.6f}")
    st.info("Tip: Drag the pin on the map to fine-tune, or type coordinates in the fields.")

st.title("📍 Chisheu EXIF Precision Tool")

uploaded_file = st.file_uploader("Upload JPEG Photo", type=["jpg", "jpeg"], key=f"up_{st.session_state.uploader_key}")

if uploaded_file:
    img = Image.open(uploaded_file)
    
    # Auto-initialize coordinates from file metadata if state is 0
    if st.session_state.lat == 0.0 and st.session_state.lon == 0.0:
        try:
            exif_dict = piexif.load(img.info.get('exif', b''))
            st.session_state.lat, st.session_state.lon = parse_exif_gps(exif_dict.get("GPS", {}))
        except:
            st.session_state.lat, st.session_state.lon = 25.7617, -80.1918 # Default to Miami if no GPS

    # Two-Column Layout
    col_map, col_info = st.columns([1.6, 1])

    with col_map:
        st.subheader("Map Fine-Tuning")
        # Initialize Folium Map
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16)
        
        # Add Draggable Marker
        folium.Marker(
            [st.session_state.lat, st.session_state.lon],
            draggable=True,
            tooltip="Drag me!",
            icon=folium.Icon(color='red', icon='crosshairs', prefix='fa')
        ).add_to(m)
        
        # Render map and capture interaction
        # width=None + use_container_width=True makes it responsive for mobile
        map_data = st_folium(m, height=500, width=None, key="main_map")

        # Sync Map Drag -> Session State -> Fields
        if map_data and map_data.get("last_object_clicked"):
            new_lat = map_data["last_object_clicked"]["lat"]
            new_lon = map_data["last_object_clicked"]["lng"]
            # Small epsilon check to avoid infinite rerun loops
            if round(new_lat, 6) != round(st.session_state.lat, 6):
                st.session_state.lat = new_lat
                st.session_state.lon = new_lon
                st.rerun()

    with col_info:
        st.image(img, use_container_width=True, caption="Current Photo")
        
        st.divider()
        mode = st.radio("Entry Format", ["Decimal", "DMS"], horizontal=True)

        if mode == "Decimal":
            new_lat_input = st.number_input("Lat", value=st.session_state.lat, format="%.6f", step=0.000001)
            new_lon_input = st.number_input("Lon", value=st.session_state.lon, format="%.6f", step=0.000001)
            
            if new_lat_input != st.session_state.lat or new_lon_input != st.session_state.lon:
                st.session_state.lat = new_lat_input
                st.session_state.lon = new_lon_input
                st.rerun()
        
        else:
            # DMS ENTRY LOGIC
            d_lat, m_lat, s_lat = decimal_to_dms(st.session_state.lat)
            d_lon, m_lon, s_lon = decimal_to_dms(st.session_state.lon)
            
            st.write("**Latitude**")
            r1c1, r1c2, r1c3, r1c4 = st.columns([1, 1, 1, 1.2])
            lat_dir = r1c1.selectbox("Dir", ["N", "S"], index=0 if st.session_state.lat >= 0 else 1)
            lat_d = r1c2.number_input("D", value=d_lat, key="ld")
            lat_m = r1c3.number_input("M", value=m_lat, key="lm")
            lat_s = r1c4.number_input("S", value=s_lat, format="%.3f", key="ls")
            
            st.write("**Longitude**")
            r2c1, r2c2, r2c3, r2c4 = st.columns([1, 1, 1, 1.2])
            lon_dir = r2c1.selectbox("Dir", ["E", "W"], index=0 if st.session_state.lon >= 0 else 1)
            lon_d = r2c2.number_input("D", value=d_lon, key="od")
            lon_m = r2c3.number_input("M", value=m_lon, key="om")
            lon_s = r2c4.number_input("S", value=s_lon, format="%.3f", key="os")

            # Update state if DMS fields change
            calc_lat = dms_to_decimal(lat_d, lat_m, lat_s, lat_dir)
            calc_lon = dms_to_decimal(lon_d, lon_m, lon_s, lon_dir)
            if round(calc_lat, 6) != round(st.session_state.lat, 6):
                st.session_state.lat = calc_lat
                st.session_state.lon = calc_lon
                st.rerun()

        # Final Processing
        if st.button("💾 Apply & Download", type="primary", use_container_width=True):
            try:
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
                st.download_button(
                    label="Download Geotagged Image",
                    data=buf.getvalue(),
                    file_name=f"fixed_{uploaded_file.name}",
                    mime="image/jpeg",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error saving EXIF: {e}")
