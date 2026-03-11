import streamlit as st
import piexif
from PIL import Image
import io
import folium
from streamlit_folium import st_folium

# --- INITIALIZE SESSION STATE ---
if 'is_modified' not in st.session_state:
    st.session_state.is_modified = False
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- RESET FUNCTION ---
def reset_app():
    st.session_state.is_modified = False
    st.session_state.uploader_key += 1

# --- CONVERSION UTILITIES ---
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
    return d, m, round(s, 3) # Precision to 3 decimal places

def parse_exif_gps(gps_data):
    def to_float(num_tuple):
        return num_tuple[0] / num_tuple[1]
    try:
        lat_dec = to_float(gps_data[2][0]) + to_float(gps_data[2][1])/60 + to_float(gps_data[2][2])/3600
        if gps_data[1].decode() == 'S': lat_dec = -lat_dec
        lon_dec = to_float(gps_data[4][0]) + to_float(gps_data[4][1])/60 + to_float(gps_data[4][2])/3600
        if gps_data[3].decode() == 'W': lon_dec = -lon_dec
        return lat_dec, lon_dec
    except:
        return 0.0, 0.0

# --- APP UI ---
st.set_page_config(layout="wide", page_title="Chisheu EXIF Tool")

with st.sidebar:
    st.title("⚙️ Controls")
    if st.button("🔄 Reset / New Photo", on_click=reset_app, use_container_width=True):
        st.rerun()
    
    st.divider()
    if st.session_state.is_modified:
        st.success("✅ Changes Detected")
    else:
        st.info("⏳ Waiting for input")

st.title("📸 Precision GPS Editor")
st.write("Upload a photo to modify its embedded location data for `chisheu.com`.")

uploaded_file = st.file_uploader(
    "Choose a JPEG", 
    type=["jpg", "jpeg"], 
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_file:
    img = Image.open(uploaded_file)
    exif_dict = piexif.load(img.info.get('exif', b''))
    init_lat, init_lon = parse_exif_gps(exif_dict.get("GPS", {}))

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.image(img, use_container_width=True, caption=f"Source: {uploaded_file.name}")
        
        # Map Preview
        st.subheader("Map Preview")
        map_placeholder = st.empty()

    with col_right:
        st.subheader("Coordinate Entry")
        mode = st.radio("Entry Method", ["Decimal Degrees", "DMS (Deg, Min, Sec)"], horizontal=True)
        
        final_lat, final_lon = 0.0, 0.0

        if mode == "Decimal Degrees":
            final_lat = st.number_input("Latitude", value=init_lat, format="%.6f", 
                                        on_change=lambda: st.session_state.update({"is_modified": True}))
            final_lon = st.number_input("Longitude", value=init_lon, format="%.6f",
                                        on_change=lambda: st.session_state.update({"is_modified": True}))
        else:
            d_lat, m_lat, s_lat = decimal_to_dms(init_lat)
            d_lon, m_lon, s_lon = decimal_to_dms(init_lon)
            
            # --- DMS UI ---
            st.write("**Latitude**")
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1.5])
            lat_dir = c1.selectbox("Dir", ["N", "S"], index=0 if init_lat >= 0 else 1)
            lat_d = c2.number_input("Deg", value=d_lat, key="lat_d")
            lat_m = c3.number_input("Min", value=m_lat, key="lat_m")
            lat_s = c4.number_input("Sec", value=s_lat, format="%.3f", key="lat_s") # 3 decimal places
            
            st.write("**Longitude**")
            c5, c6, c7, c8 = st.columns([1.5, 1, 1, 1.5])
            lon_dir = c5.selectbox("Dir", ["E", "W"], index=0 if init_lon >= 0 else 1)
            lon_d = c6.number_input("Deg", value=d_lon, key="lon_d")
            lon_m = c7.number_input("Min", value=m_lon, key="lon_m")
            lon_s = c8.number_input("Sec", value=s_lon, format="%.3f", key="lon_s") # 3 decimal places
            
            final_lat = dms_to_decimal(lat_d, lat_m, lat_s, lat_dir)
            final_lon = dms_to_decimal(lon_d, lon_m, lon_s, lon_dir)
            
            # Check for changes in DMS mode
            if final_lat != init_lat or final_lon != init_lon:
                st.session_state.is_modified = True

        # Update Map
        m = folium.Map(location=[final_lat, final_lon], zoom_start=14)
        folium.Marker([final_lat, final_lon], popup="Target Location").add_to(m)
        with map_placeholder:
            st_folium(m, height=350, key="preview_map", returned_objects=[])

        # Save Action
        st.divider()
        if st.button("🔥 Apply Changes & Download", type="primary", use_container_width=True):
            def to_exif_rational(val):
                d, m, s = decimal_to_dms(val)
                # We multiply seconds by 1000 to preserve the 3 decimal places in the rational fraction
                return ((d, 1), (m, 1), (int(round(s * 1000)), 1000))

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: 'N' if final_lat >= 0 else 'S',
                piexif.GPSIFD.GPSLatitude: to_exif_rational(final_lat),
                piexif.GPSIFD.GPSLongitudeRef: 'E' if final_lon >= 0 else 'W',
                piexif.GPSIFD.GPSLongitude: to_exif_rational(final_lon),
            }
            
            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif_bytes)
            
            st.download_button(
                label="💾 Download Updated Photo",
                data=buf.getvalue(),
                file_name=f"geotagged_{uploaded_file.name}",
                mime="image/jpeg",
                use_container_width=True
            )
