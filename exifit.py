import streamlit as st
import piexif
from PIL import Image
import io
import zipfile
import folium
from streamlit_folium import st_folium

# --- INITIALIZE SESSION STATE ---
if 'processed_files' not in st.session_state:
    st.session_state.processed_files = {}

# --- RESET FUNCTION ---
def reset_app():
    st.session_state.processed_files = {}
    # We use a session state 'counter' to force the file uploader to refresh
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0
    st.session_state.uploader_key += 1

# --- UTILITIES ---
def decimal_to_exif(degree):
    abs_degree = abs(degree)
    d = int(abs_degree)
    m = int((abs_degree - d) * 60)
    s = int((abs_degree - d - m/60) * 3600 * 100)
    return ((d, 1), (m, 1), (s, 100))

# --- APP UI ---
st.set_page_config(layout="wide", page_title="Chisheu EXIF Tool")

# Sidebar Controls
with st.sidebar:
    st.title("🛠️ Batch Controls")
    if st.button("🔄 Reset All / Clear Uploads", on_click=reset_app, use_container_width=True):
        st.rerun()
    
    st.divider()
    
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0

st.title("📸 Photo GPS Batch Editor")
st.write("Modify up to 5 photos at once for `chisheu.com`.")

uploaded_files = st.file_uploader(
    "Upload JPEGs", 
    type=["jpg", "jpeg"], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    files_to_process = uploaded_files[:5]
    modified_images = [] 

    # Progress Calculation
    done_count = sum(1 for f in files_to_process if st.session_state.processed_files.get(f.name))
    progress_text = f"Modification Progress: {done_count}/{len(files_to_process)} photos"
    st.progress(done_count / len(files_to_process), text=progress_text)

    if done_count == len(files_to_process):
        st.balloons()
        st.success("All photos modified! Ready for batch download.")

    st.divider()

    for i, file in enumerate(files_to_process):
        is_done = st.session_state.processed_files.get(file.name, False)
        
        # Expander logic: Collapse if done, expand if not
        with st.expander(f"{'✅' if is_done else '⏳'} {file.name}", expanded=not is_done):
            col_img, col_map, col_input = st.columns([1, 1, 1.2])
            
            img = Image.open(file)
            with col_img:
                st.image(img, use_container_width=True)
            
            with col_input:
                st.markdown("### Metadata Entry")
                lat = st.number_input(f"Latitude", value=0.0, format="%.6f", key=f"lat{i}", 
                                      on_change=lambda f=file.name: st.session_state.processed_files.update({f: True}))
                lon = st.number_input(f"Longitude", value=0.0, format="%.6f", key=f"lon{i}",
                                      on_change=lambda f=file.name: st.session_state.processed_files.update({f: True}))
                
                if is_done:
                    st.info("Status: Metadata Staged")

            with col_map:
                m = folium.Map(location=[lat, lon], zoom_start=12)
                folium.Marker([lat, lon]).add_to(m)
                st_folium(m, height=250, key=f"map{i}", returned_objects=[])

            # Generate Metadata Bytes
            exif_dict = piexif.load(img.info.get('exif', b''))
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
                piexif.GPSIFD.GPSLatitude: decimal_to_exif(lat),
                piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
                piexif.GPSIFD.GPSLongitude: decimal_to_exif(lon),
            }
            exif_dict["GPS"] = gps_ifd
            exif_bytes = piexif.dump(exif_dict)
            
            buf = io.BytesIO()
            img.save(buf, format="JPEG", exif=exif_bytes)
            modified_images.append((file.name, buf.getvalue()))

    # --- ZIP EXPORT ---
    if done_count > 0:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for name, data in modified_images:
                zip_file.writestr(name, data)
        
        st.download_button(
            label=f"📦 Download {done_count} Modified Photos (.zip)",
            data=zip_buffer.getvalue(),
            file_name="chisheu_batch_exif.zip",
            mime="application/zip",
            use_container_width=True
        )
