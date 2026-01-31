import streamlit as st
from PIL import Image
from ui.components.image_creator import load_user_images


def render_image_gallery_tab(username: str):
    """Display user's generated image gallery with history and download options"""
    st.header("🖼️ Galería de Imágenes Generadas")

    if not username:
        st.warning("Debes iniciar sesión para ver tu galería de imágenes")
        return

    # Load user images
    images_info = load_user_images(username)

    if not images_info:
        st.info("🎨 Aún no has generado ninguna imagen. Ve a la pestaña 'Generar Imágenes' para crear tu primera imagen.")
        return

    # Show statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Imágenes", len(images_info))
    with col2:
        modes = [img["mode"] for img in images_info if img["mode"]]
        if modes:
            most_used_mode = max(set(modes), key=modes.count)
            st.metric("Modo más usado", most_used_mode)
    with col3:
        models = [img["model"] for img in images_info if img["model"]]
        if models:
            st.metric("Imágenes únicas", len(set(models)))

    st.divider()

    # Filter options
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("🔍 Buscar por prompt", placeholder="Escribe palabras clave...")
    with col2:
        view_mode = st.selectbox("Vista", ["Galería", "Tabla"])

    # Filter images by search
    filtered_images = images_info
    if search_query:
        filtered_images = [
            img for img in images_info
            if search_query.lower() in img["prompt"].lower()
        ]

    if not filtered_images:
        st.warning(f"No se encontraron imágenes que contengan '{search_query}'")
        return

    st.info(f"Mostrando {len(filtered_images)} de {len(images_info)} imágenes")

    # Gallery view
    if view_mode == "Galería":
        render_gallery_view(filtered_images)
    else:
        render_table_view(filtered_images)


def render_gallery_view(images_info: list):
    """Render images in a grid gallery format"""
    # Show images in grid (3 per row)
    cols_per_row = 3

    for i in range(0, len(images_info), cols_per_row):
        cols = st.columns(cols_per_row)

        for j, col in enumerate(cols):
            if i + j < len(images_info):
                img_info = images_info[i + j]

                with col:
                    # Load and display image
                    try:
                        image = Image.open(img_info["path"])
                        st.image(image)
                    except Exception as e:
                        st.error(f"Error al cargar imagen: {e}")
                        continue

                    # Show metadata in expander
                    with st.expander("📝 Detalles"):
                        st.caption(f"**Fecha:** {img_info['timestamp'][:10] if img_info['timestamp'] else 'N/A'}")
                        st.caption(f"**Modelo:** {img_info['model']}")
                        st.caption(f"**Modo:** {img_info['mode']}")

                        if img_info["prompt"]:
                            st.text_area(
                                "Prompt",
                                value=img_info["prompt"],
                                height=80,
                                disabled=True,
                                key=f"prompt_{img_info['filename']}"
                            )

                        if img_info["negative_prompt"]:
                            st.text_area(
                                "Prompt Negativo",
                                value=img_info["negative_prompt"],
                                height=60,
                                disabled=True,
                                key=f"neg_{img_info['filename']}"
                            )

                        # Show config details
                        config = img_info.get("config", {})
                        if config:
                            st.caption("**Configuración:**")
                            config_text = "\n".join([f"- {k}: {v}" for k, v in config.items() if k not in ["seed"]])
                            st.text(config_text)

                    # Download button
                    with open(img_info["path"], "rb") as f:
                        st.download_button(
                            "⬇️ Descargar",
                            data=f.read(),
                            file_name=img_info["filename"],
                            mime="image/png",
                            width="stretch",
                            key=f"download_{img_info['filename']}"
                        )


def render_table_view(images_info: list):
    """Render images in a table format with thumbnails"""
    for img_info in images_info:
        with st.container():
            col1, col2 = st.columns([1, 3])

            with col1:
                # Thumbnail
                try:
                    image = Image.open(img_info["path"])
                    st.image(image)
                except Exception as e:
                    st.error(f"Error: {e}")

            with col2:
                # Metadata
                st.markdown(f"**{img_info['filename']}**")
                st.caption(f"📅 {img_info['timestamp'][:19] if img_info['timestamp'] else 'N/A'}")
                st.caption(f"🤖 {img_info['model']}")
                st.caption(f"🎨 {img_info['mode']}")

                if img_info["prompt"]:
                    with st.expander("Ver prompt completo"):
                        st.text(img_info["prompt"])
                        if img_info["negative_prompt"]:
                            st.text(f"Negativo: {img_info['negative_prompt']}")

                # Download button
                with open(img_info["path"], "rb") as f:
                    st.download_button(
                        "⬇️ Descargar",
                        data=f.read(),
                        file_name=img_info["filename"],
                        mime="image/png",
                        key=f"download_table_{img_info['filename']}"
                    )

            st.divider()

