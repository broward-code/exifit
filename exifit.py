import streamlit as st
import piexif
from PIL import Image
import io
import folium
from streamlit_folium import st_folium

# --- 1. SESSION STATE MANAGEMENT ---
# This keeps the coordinates synced between the map and the text fields
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

# --- 2. UTILITIES ---
def decimal_to_exif_rational(val):
    """Converts decimal to EXIF rational with 3-decimal precision."""
    abs_val = abs(val)
    d = int(abs_val)
    m = int((abs_val - d) * 60)
    s = (abs_val - d - m/60) * 3600
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
st.set_page_config(layout="wide", page_title="Chisheu EXIF Precision Tool")

with st.sidebar:
    st.title("⚙️ Controls")
    st.button("🔄 Reset / New Photo", on_click=reset_app, use_container_width=True)
    st.info("Tip: Enter coordinates manually to 'teleport' the pin, then drag the pin to fine-tune.")

st.title("📸 Interactive GPS Fine-Tuner")

uploaded_file = st.file_uploader("Upload JPEG", type=["jpg", "jpeg"], key=f"up_{st.session_state.uploader_key}")

if uploaded_file:
    img = Image.open(uploaded_file)
    
    # Initialize state from file only if state is currently zero
    if st.session_state.lat == 0.0 and st.session_state.lon == 0.0:
        exif_dict = piexif.load(img.info.get('exif', b''))
        file_lat, file_lon = parse_exif_gps(exif_dict.get("GPS", {}))
        st.session_state.lat = file_lat
        st.session_state.lon = file_lon

    col_map, col_ctrl = st.columns([1.5, 1])

    with col_ctrl:
        st.subheader("Manual Coordinate Entry")
        # Manual Inputs update the Session State immediately
        lat_input = st.number_input("Latitude", value=st.session_state.lat, format="%.6f", key="manual_lat")
        lon_input = st.number_input("Longitude", value=st.session_state.lon, format="%.6f", key="manual_lon")
        
        # If the user typed something new, update the global state
        if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
            st.session_state.lat = lat_input
            st.session_state.lon = lon_input
            st.rerun()

        st.image(img, use_container_width=True, caption="Preview")

    with col_map:
        st.subheader("Map Fine-Tuning")
        st.caption("Drag the blue marker to adjust placement precisely.")
        
        # Create map centered on current state
        m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16)
        
        # Add the draggable marker
        marker = folium.Marker(
            [st.session_state.lat, st.session_state.lon],
            draggable=True,
            icon=folium.Icon(color='blue', icon='info-sign')
        )
        marker.add_to(m)
        
        # Capture the move event
        # 'returned_objects' tells Streamlit which map data to send back to Python
        map_data = st_folium(m, height=500, width=None, key="fine_tune_map")

        # Logic: If the pin was dragged, update the coordinates in the fields
        if map_data and map_data.get("last_object_clicked"):
            dragged_lat = map_data["last_object_clicked"]["lat"]
            dragged_lon = map_data["last_object_clicked"]["lng"]
            
            # Check if the drag is different enough to warrant a state update
            if round(dragged_lat, 6) != round(st.session_state.lat, 6):
                st.session_state.lat = dragged_lat
                st.session_state.lon = dragged_lon
                st.rerun()

    # --- 4. FINAL EXPORT ---
    if st.button("🔥 Apply Fine-Tuning & Download", type="primary", use_container_width=True):
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
        st.download_button("💾 Download Updated Photo", buf.getvalue(), f"fixed_{uploaded_file.name}", "image/jpeg")
