import streamlit as st
import boto3
import json
import base64
import io
from pathlib import Path
from datetime import datetime
from PIL import Image
from botocore.config import Config

PROMPT_EXAMPLES = {
    "subject": [
        "Un majestuoso lobo blanco aullando a la luna",
        "Un antiguo roble con ramas retorcidas",
        "Un paisaje urbano cyberpunk futurista",
        "Una joven mujer con cabello rojo flotante"
    ],
    "style": [
        "Pintura al óleo, estilo impresionista",
        "Arte digital, hiperrealista",
        "Ilustración en acuarela",
        "Render 3D, estilo animación Pixar"
    ],
    "environment": [
        "Bosque profundo con niebla matutina",
        "Estación espacial abandonada flotando en órbita",
        "Cafetería acogedora en un día lluvioso",
        "Arrecife de coral submarino al atardecer"
    ],
    "atmosphere": [
        "Misterioso y etéreo",
        "Cálido y nostálgico",
        "Oscuro y distópico",
        "Brillante y alegre"
    ],
    "details": [
        "Patrones intrincados en la ropa, texturas visibles",
        "Partículas de polvo flotando en rayos de luz",
        "Gotas de lluvia en el cristal, reflejos",
        "Hojas de otoño caídas, gotas de rocío"
    ],
    "camera": [
        "Canon EOS R5, 85mm f/1.4",
        "Sony A7IV, 35mm f/1.8 gran angular",
        "Hasselblad formato medio, 50mm",
        "iPhone 15 Pro, lente ultra gran angular"
    ],
    "lighting": [
        "Hora dorada, contraluz cálido",
        "Claroscuro dramático, fuente única",
        "Iluminación de estudio suave y difusa",
        "Luces de neón con niebla volumétrica"
    ],
    "composition": [
        "Regla de tercios, sujeto descentrado",
        "Perspectiva simétrica y centrada",
        "Ángulo holandés, líneas diagonales dinámicas",
        "Vista de pájaro, toma cenital"
    ]
}

IMAGE_MODELS = {
    "amazon.titan-image-generator-v1": {
        "name": "Amazon Titan Image Generator v1",
        "supports_image_to_image": True,
        "max_size": 1024
    },
    "amazon.titan-image-generator-v2:0": {
        "name": "Amazon Titan Image Generator v2",
        "supports_image_to_image": True,
        "max_size": 1024
    },
    "stability.stable-diffusion-xl-v1": {
        "name": "Stable Diffusion XL v1",
        "supports_image_to_image": True,
        "max_size": 1024
    },
    "stability.sd3-large-v1:0": {
        "name": "Stable Diffusion 3 Large",
        "supports_image_to_image": False,
        "max_size": 1024
    },
    "stability.stable-image-core-v1:0": {
        "name": "Stable Image Core",
        "supports_image_to_image": False,
        "max_size": 1024
    },
    "stability.stable-image-ultra-v1:0": {
        "name": "Stable Image Ultra",
        "supports_image_to_image": False,
        "max_size": 1024
    }
}


def load_aws_credentials() -> dict:
    """Load AWS credentials from Streamlit secrets"""
    return {
        "aws_access_key_id": st.secrets.get("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": st.secrets.get("AWS_SECRET_ACCESS_KEY"),
        "region": st.secrets.get("AWS_REGION", "us-east-1")
    }



def get_bedrock_client(credentials: dict):
    config = Config(
        read_timeout=300,
        connect_timeout=300,
        retries={"max_attempts": 3}
    )
    return boto3.client(
        "bedrock-runtime",
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
        region_name=credentials.get("region", "us-east-1"),
        config=config
    )


def get_bedrock_management_client(credentials: dict):
    return boto3.client(
        "bedrock",
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
        region_name=credentials.get("region", "us-east-1")
    )


def get_available_image_models(bedrock_mgmt_client) -> list:
    available = []
    try:
        response = bedrock_mgmt_client.list_foundation_models(
            byOutputModality="IMAGE"
        )
        for model in response.get("modelSummaries", []):
            model_id = model.get("modelId", "")
            if model_id in IMAGE_MODELS:
                available.append({
                    "id": model_id,
                    "name": IMAGE_MODELS[model_id]["name"],
                    "supports_i2i": IMAGE_MODELS[model_id]["supports_image_to_image"]
                })
    except Exception as e:
        st.warning(f"Could not fetch models: {e}. Using default list.")
        for model_id, info in IMAGE_MODELS.items():
            available.append({
                "id": model_id,
                "name": info["name"],
                "supports_i2i": info["supports_image_to_image"]
            })
    return available


def build_prompt(fields: dict) -> str:
    parts = []
    if fields.get("subject"):
        parts.append(fields["subject"])
    if fields.get("style"):
        parts.append(f"en {fields['style']}")
    if fields.get("environment"):
        parts.append(f"ambientado en {fields['environment']}")
    if fields.get("atmosphere"):
        parts.append(f"wcon una {fields['atmosphere']} atmosphere")
    if fields.get("details"):
        parts.append(f", incluir  {fields['details']}")
    if fields.get("camera"):
        parts.append(f", imitar una {fields['camera']}")
    if fields.get("lighting"):
        parts.append(f"usando {fields['lighting']}")
    if fields.get("composition"):
        parts.append(f", componer con  {fields['composition']}")
    return ", ".join(parts) + "."


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_image_titan(client, model_id: str, prompt: str, negative_prompt: str,
                         config: dict, input_image: str = None) -> bytes:
    body = {
        "textToImageParams": {"text": prompt},
        "taskType": "TEXT_IMAGE"
    }

    if input_image:
        body["taskType"] = "IMAGE_VARIATION"
        body["imageVariationParams"] = {
            "text": prompt,
            "images": [input_image],
            "similarityStrength": config.get("similarity_strength", 0.7)
        }
        del body["textToImageParams"]

    body["imageGenerationConfig"] = {
        "numberOfImages": 1,
        "height": config.get("height", 1024),
        "width": config.get("width", 1024),
        "cfgScale": config.get("cfg_scale", 8.0)
    }

    if negative_prompt:
        if "textToImageParams" in body:
            body["textToImageParams"]["negativeText"] = negative_prompt
        elif "imageVariationParams" in body:
            body["imageVariationParams"]["negativeText"] = negative_prompt

    if config.get("seed"):
        body["imageGenerationConfig"]["seed"] = config["seed"]

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return base64.b64decode(result["images"][0])


def generate_image_sdxl(client, model_id: str, prompt: str, negative_prompt: str,
                        config: dict, input_image: str = None) -> bytes:
    body = {
        "text_prompts": [{"text": prompt, "weight": 1.0}],
        "cfg_scale": config.get("cfg_scale", 7),
        "steps": config.get("steps", 50),
        "height": config.get("height", 1024),
        "width": config.get("width", 1024)
    }

    if negative_prompt:
        body["text_prompts"].append({"text": negative_prompt, "weight": -1.0})

    if config.get("seed"):
        body["seed"] = config["seed"]

    if input_image:
        body["init_image"] = input_image
        body["init_image_mode"] = "IMAGE_STRENGTH"
        body["image_strength"] = config.get("image_strength", 0.35)

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return base64.b64decode(result["artifacts"][0]["base64"])


def generate_image_sd3(client, model_id: str, prompt: str, negative_prompt: str,
                       config: dict) -> bytes:
    body = {
        "prompt": prompt,
        "mode": "text-to-image",
        "aspect_ratio": config.get("aspect_ratio", "1:1"),
        "output_format": "png"
    }

    if negative_prompt:
        body["negative_prompt"] = negative_prompt

    if config.get("seed"):
        body["seed"] = config["seed"]

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return base64.b64decode(result["images"][0])


def generate_image(client, model_id: str, prompt: str, negative_prompt: str,
                   config: dict, input_image: str = None) -> bytes:
    if "titan" in model_id.lower():
        return generate_image_titan(client, model_id, prompt, negative_prompt, config, input_image)
    elif "stable-diffusion-xl" in model_id.lower():
        return generate_image_sdxl(client, model_id, prompt, negative_prompt, config, input_image)
    elif "sd3" in model_id.lower() or "stable-image" in model_id.lower():
        return generate_image_sd3(client, model_id, prompt, negative_prompt, config)
    else:
        raise ValueError(f"Unsupported model: {model_id}")


def show_help_popover(field_name: str, examples: list):
    with st.popover("?"):
        st.markdown(f"**Ejemplos para {field_name}:**")
        for i, ex in enumerate(examples, 1):
            st.markdown(f"{i}. {ex}")


def save_generated_image(username: str, image_bytes: bytes, metadata: dict) -> Path:
    """
    Save generated image to user's images folder with metadata.
    Returns the path to the saved image.
    """
    # Create user's images directory (following runs/{username} pattern)
    user_images_dir = Path("runs") / username / "images"
    user_images_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"imagen_{timestamp}.png"
    image_path = user_images_dir / image_filename

    # Save image
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    # Save metadata as JSON
    metadata_path = user_images_dir / f"imagen_{timestamp}_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return image_path


def load_user_images(username: str) -> list:
    """
    Load all images and their metadata for a user.
    Returns list of dicts with image info.
    """
    user_images_dir = Path("runs") / username / "images"
    if not user_images_dir.exists():
        return []

    images_info = []

    # Get all PNG files
    for image_path in sorted(user_images_dir.glob("imagen_*.png"), reverse=True):
        # Load corresponding metadata
        metadata_path = image_path.parent / f"{image_path.stem}_metadata.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        images_info.append({
            "path": image_path,
            "filename": image_path.name,
            "timestamp": metadata.get("timestamp", ""),
            "prompt": metadata.get("prompt", ""),
            "negative_prompt": metadata.get("negative_prompt", ""),
            "model": metadata.get("model", ""),
            "config": metadata.get("config", {}),
            "mode": metadata.get("mode", "")
        })

    return images_info


def render_image_generator_tab(username: str):
    st.header("Generador de Imágenes - AWS Bedrock")

    if not username:
        st.warning("Debes iniciar sesión para usar el generador de imágenes")
        return

    try:
        credentials = load_aws_credentials()
        if not credentials.get("aws_access_key_id") or not credentials.get("aws_secret_access_key"):
            st.error("No se encontraron credenciales de AWS en los secretos de Streamlit")
            st.info("Configura AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y AWS_REGION en .streamlit/secrets.toml")
            return
        st.success("✓ Credenciales AWS cargadas")
    except Exception as e:
        st.error(f"Error al cargar credenciales: {e}")
        return

    try:
        bedrock_client = get_bedrock_client(credentials)
        bedrock_mgmt = get_bedrock_management_client(credentials)
        available_models = get_available_image_models(bedrock_mgmt)
    except Exception as e:
        st.error(f"Error al conectar con AWS Bedrock: {e}")
        return

    if not available_models:
        st.warning("No hay modelos de generación de imágenes disponibles")
        return

    col_mode, col_model = st.columns(2)
    with col_mode:
        mode = st.radio("Modo de Generación", ["Texto a Imagen", "Imagen a Imagen"], horizontal=True)

    with col_model:
        if mode == "Imagen a Imagen":
            i2i_models = [m for m in available_models if m["supports_i2i"]]
            if not i2i_models:
                st.warning("Ningún modelo soporta Imagen a Imagen")
                return
            model_options = {m["name"]: m["id"] for m in i2i_models}
        else:
            model_options = {m["name"]: m["id"] for m in available_models}

        selected_model_name = st.selectbox("Modelo", list(model_options.keys()))
        selected_model_id = model_options[selected_model_name]

    input_image_b64 = None
    if mode == "Imagen a Imagen":
        st.subheader("Imagen de Entrada")
        uploaded_file = st.file_uploader("Subir imagen", type=["png", "jpg", "jpeg", "webp"])
        if uploaded_file:
            input_image = Image.open(uploaded_file).convert("RGB")
            st.image(input_image, caption="Imagen de Entrada", width=300)
            input_image_b64 = image_to_base64(input_image)

    st.subheader("Constructor de Prompt")
    st.caption("Construye tu prompt usando la fórmula. Haz clic en ? para ver ejemplos.")

    prompt_fields = {}

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["subject"] = st.text_input("Sujeto", placeholder="¿Cuál es el sujeto principal?")
    with col2:
        st.write("")
        show_help_popover("Sujeto", PROMPT_EXAMPLES["subject"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["style"] = st.text_input("Estilo/Técnica", placeholder="Estilo artístico o técnica")
    with col2:
        st.write("")
        show_help_popover("Estilo", PROMPT_EXAMPLES["style"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["environment"] = st.text_input("Ambiente/Escenario", placeholder="¿Dónde está la escena?")
    with col2:
        st.write("")
        show_help_popover("Ambiente", PROMPT_EXAMPLES["environment"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["atmosphere"] = st.text_input("Atmósfera/Ánimo", placeholder="¿Qué sentimiento debe evocar?")
    with col2:
        st.write("")
        show_help_popover("Atmósfera", PROMPT_EXAMPLES["atmosphere"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["details"] = st.text_input("Detalles", placeholder="Detalles específicos a incluir")
    with col2:
        st.write("")
        show_help_popover("Detalles", PROMPT_EXAMPLES["details"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["camera"] = st.text_input("Cámara + Apertura", placeholder="Cámara y configuración de lente")
    with col2:
        st.write("")
        show_help_popover("Cámara", PROMPT_EXAMPLES["camera"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["lighting"] = st.text_input("Estilo de Iluminación", placeholder="Configuración de iluminación")
    with col2:
        st.write("")
        show_help_popover("Iluminación", PROMPT_EXAMPLES["lighting"])

    col1, col2 = st.columns([0.95, 0.05])
    with col1:
        prompt_fields["composition"] = st.text_input("Composición/Perspectiva", placeholder="Reglas de composición")
    with col2:
        st.write("")
        show_help_popover("Composición", PROMPT_EXAMPLES["composition"])

    built_prompt = build_prompt(prompt_fields)

    st.subheader("Prompt Generado")
    final_prompt = st.text_area("Editar o usar tal cual", value=built_prompt, height=100)

    negative_prompt = st.text_input("Prompt Negativo", placeholder="Qué evitar en la imagen")

    with st.expander("Configuración de Imagen"):
        col1, col2, col3 = st.columns(3)

        with col1:
            if "sd3" in selected_model_id or "stable-image" in selected_model_id:
                aspect_ratio = st.selectbox("Relación de Aspecto",
                                            ["1:1", "16:9", "21:9", "2:3", "3:2", "4:5", "5:4", "9:16", "9:21"])
                width, height = 1024, 1024
            else:
                width = st.selectbox("Ancho", [512, 768, 1024], index=2)
                height = st.selectbox("Alto", [512, 768, 1024], index=2)
                aspect_ratio = "1:1"

        with col2:
            cfg_scale = st.slider("Escala CFG", 1.0, 20.0, 8.0, 0.5)
            if "stable-diffusion-xl" in selected_model_id:
                steps = st.slider("Pasos", 10, 150, 50)
            else:
                steps = 50

        with col3:
            use_seed = st.checkbox("Usar Semilla")
            seed = st.number_input("Semilla", 0, 2147483647, 42) if use_seed else None

            if mode == "Imagen a Imagen":
                if "titan" in selected_model_id:
                    similarity = st.slider("Fuerza de Similitud", 0.2, 1.0, 0.7, 0.1)
                else:
                    image_strength = st.slider("Fuerza de Imagen", 0.0, 1.0, 0.35, 0.05)

    gen_config = {
        "width": width,
        "height": height,
        "cfg_scale": cfg_scale,
        "steps": steps,
        "seed": seed,
        "aspect_ratio": aspect_ratio
    }

    if mode == "Imagen a Imagen":
        if "titan" in selected_model_id:
            gen_config["similarity_strength"] = similarity
        else:
            gen_config["image_strength"] = image_strength

    if st.button("Generar Imagen", type="primary", width="stretch"):
        if not final_prompt.strip():
            st.warning("Por favor ingresa un prompt")
            return

        if mode == "Imagen a Imagen" and not input_image_b64:
            st.warning("Por favor sube una imagen de entrada")
            return

        with st.spinner("Generando imagen..."):
            try:
                image_bytes = generate_image(
                    bedrock_client,
                    selected_model_id,
                    final_prompt,
                    negative_prompt,
                    gen_config,
                    input_image_b64
                )

                generated_image = Image.open(io.BytesIO(image_bytes))
                st.image(generated_image, caption="Imagen Generada")

                # Save image with metadata
                metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "prompt": final_prompt,
                    "negative_prompt": negative_prompt,
                    "model": selected_model_name,
                    "model_id": selected_model_id,
                    "mode": mode,
                    "config": gen_config
                }

                saved_path = save_generated_image(username, image_bytes, metadata)
                st.success(f"✅ Imagen guardada en tu galería personal")

                st.download_button(
                    "Descargar Imagen",
                    data=image_bytes,
                    file_name="imagen_generada.png",
                    mime="image/png"
                )

            except Exception as e:
                st.error(f"Falló la generación: {e}")



