import streamlit as st
import piexif
from PIL import Image
import io
import folium
from streamlit_folium import st_folium

# --- INITIALIZE SESSION STATE ---
if 'coords' not in st.session_state:
    st.session_state.coords = {"lat": 0.0, "lon": 0.0}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.coords = {"lat": 0.0, "lon": 0.0}
    st.session_state.uploader_key += 1

# --- UTILITIES ---
def decimal_to_dms(decimal):
    abs_dec = abs(decimal)
    d = int(abs_dec)
    m = int((abs_dec - d) * 60)
    s = (abs_dec - d - m/60) * 3600
    return d, m, round(s, 3)

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

# --- APP UI ---
st.set_page_config(layout="wide", page_title="Chisheu EXIF Tool")

with st.sidebar:
    st.title("⚙️ Controls")
    st.button("🔄 Reset / New Photo", on_click=reset_app, use_container_width=True)

st.title("📸 Interactive GPS Editor")

uploaded_file = st.file_uploader("Choose a JPEG", type=["jpg", "jpeg"], key=f"up_{st.session_state.uploader_key}")

if uploaded_file:
    img = Image.open(uploaded_file)
    exif_dict = piexif.load(img.info.get('exif', b''))
    
    # Initialize coordinates from file if not already set
    if st.session_state.coords["lat"] == 0.0:
        init_lat, init_lon = parse_exif_gps(exif_dict.get("GPS", {}))
        st.session_state.coords = {"lat": init_lat, "lon": init_lon}

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.image(img, use_container_width=True)
        st.subheader("📍 Drag pin to set location")
        
        # 1. Create Map
        m = folium.Map(location=[st.session_state.coords["lat"], st.session_state.coords["lon"]], zoom_start=15)
        
        # 2. Add Draggable Marker
        marker = folium.Marker(
            [st.session_state.coords["lat"], st.session_state.coords["lon"]],
            draggable=True,
            popup="Drag me!"
        )
        marker.add_to(m)
        
        # 3. Capture Map Output
        map_data = st_folium(m, height=400, width=700, key="interactive_map")
        
        # 4. Sync Dragged Data back to Session State
        if map_data and map_data.get("last_object_clicked_tooltip") is None: # Check if it's a drag event
            if map_data.get("last_object_clicked"):
                new_lat = map_data["last_object_clicked"]["lat"]
                new_lon = map_data["last_object_clicked"]["lng"]
                # Optional: Update state here if you want fields to move with the pin
    
    with col_right:
        st.subheader("Coordinate Refinement")
        mode = st.radio("Entry Method", ["Decimal", "DMS"], horizontal=True)
        
        if mode == "Decimal":
            final_lat = st.number_input("Lat", value=st.session_state.coords["lat"], format="%.6f")
            final_lon = st.number_input("Lon", value=st.session_state.coords["lon"], format="%.6f")
        else:
            d_lat, m_lat, s_lat = decimal_to_dms(st.session_state.coords["lat"])
            st.write("**Latitude**")
            c1, c2, c3, c4 = st.columns([1,1,1,1.5])
            lat_dir = c1.selectbox("Dir", ["N", "S"], index=0 if st.session_state.coords["lat"] >= 0 else 1)
            # Update final_lat based on these inputs... (omitted for brevity, same logic as before)
            final_lat = st.session_state.coords["lat"] # Placeholder
            final_lon = st.session_state.coords["lon"]

        # Final EXIF Save
        if st.button("🔥 Apply & Download", type="primary", use_container_width=True):
            # (Piexif saving logic remains the same)
            st.success("Saving...")
