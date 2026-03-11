import streamlit as st
import piexif
from PIL import Image
import io
import folium
from streamlit_folium import st_folium

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
    return d, m, round(s, 4)

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

# --- MAIN APP ---
st.set_page_config(page_title="EXIF GPS Modifier", layout="wide")
st.title("??? Photo GPS Metadata Editor & Map")

uploaded_file = st.file_uploader("Upload a JPEG Image", type=["jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    exif_dict = piexif.load(img.info.get('exif', b''))
    gps_info = exif_dict.get("GPS", {})
    init_lat, init_lon = parse_exif_gps(gps_info)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.image(img, use_container_width=True, caption="Original Photo")
        
        # --- MAP PREVIEW ---
        st.subheader("Map Preview")
        # We define this placeholder here so it updates based on the inputs below
        map_placeholder = st.empty()

    with col_right:
        st.subheader("Edit Coordinates")
        entry_mode = st.radio("Select Entry Method:", ["Decimal Degrees", "DMS (Degrees, Minutes, Seconds)"], horizontal=True)
        
        final_lat, final_lon = 0.0, 0.0

        if entry_mode == "Decimal Degrees":
            final_lat = st.number_input("Latitude", value=init_lat, format="%.6f", step=0.0001)
            final_lon = st.number_input("Longitude", value=init_lon, format="%.6f", step=0.0001)
        
        else:
            d_lat, m_lat, s_lat = decimal_to_dms(init_lat)
            d_lon, m_lon, s_lon = decimal_to_dms(init_lon)
            
            st.write("**Latitude**")
            c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
            lat_dir = c1.selectbox("Dir", ["N", "S"], index=0 if init_lat >= 0 else 1)
            lat_d = c2.number_input("Deg", value=d_lat, key="ld")
            lat_m = c3.number_input("Min", value=m_lat, key="lm")
            lat_s = c4.number_input("Sec", value=s_lat, key="ls")
            
            st.write("**Longitude**")
            c5, c6, c7, c8 = st.columns([1.5, 1, 1, 1])
            lon_dir = c5.selectbox("Dir", ["E", "W"], index=0 if init_lon >= 0 else 1)
            lon_d = c6.number_input("Deg", value=d_lon, key="lo_d")
            lon_m = c7.number_input("Min", value=m_lon, key="lo_m")
            lon_s = c8.number_input("Sec", value=s_lon, key="lo_s")
            
            final_lat = dms_to_decimal(lat_d, lat_m, lat_s, lat_dir)
            final_lon = dms_to_decimal(lon_d, lon_m, lon_s, lon_dir)

        # Update the Map in the placeholder
        m = folium.Map(location=[final_lat, final_lon], zoom_start=12)
        folium.Marker([final_lat, final_lon], popup="New Location").add_to(m)
        with map_placeholder:
            st_folium(m, height=300, width=None)

        # SAVE ACTION
        if st.button("?? Update EXIF & Download", use_container_width=True):
            def to_rational(val):
                d, m, s = decimal_to_dms(val)
                return ((d, 1), (m, 1), (int(s * 100), 100))

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: 'N' if final_lat >= 0 else 'S',
                piexif.GPSIFD.GPSLatitude: to_rational(final_lat),
                piexif.GPSIFD.GPSLongitudeRef: 'E' if final_lon >= 0 else 'W',
                piexif.GPSIFD.GPSLongitude: to_rational(final_lon),
            }
            
            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif_bytes)
            
            st.download_button(label="Download Image", data=buf.getvalue(), file_name="geotagged_output.jpg", mime="image/jpeg")
