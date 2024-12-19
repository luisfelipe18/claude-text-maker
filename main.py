import streamlit as st
import boto3
import os
import json
import requests
from anthropic import Anthropic
import tempfile
from botocore.exceptions import ClientError
import time
import uuid
from datetime import datetime

# Configuración de la página de Streamlit
st.set_page_config(
    page_title="Procesador de Videos y Transcripciones",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de estilos
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        margin-top: 10px;
    }
    .status-box {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Inicialización de las sesiones de estado
if 'transcription_status' not in st.session_state:
    st.session_state['transcription_status'] = None
if 'job_name' not in st.session_state:
    st.session_state['job_name'] = None
if 'video_url' not in st.session_state:
    st.session_state['video_url'] = None
if 'video_s3_uri' not in st.session_state:
    st.session_state['video_s3_uri'] = None
if 'processing_failed' not in st.session_state:
    st.session_state['processing_failed'] = False
if 'transcription' not in st.session_state:
    st.session_state['transcription'] = None
if 'rewritten_text' not in st.session_state:
    st.session_state['rewritten_text'] = None
if 'existing_files' not in st.session_state:
    st.session_state['existing_files'] = {}
if 'transcription' not in st.session_state:
    st.session_state['transcription'] = None
if 'rewritten_text' not in st.session_state:
    st.session_state['rewritten_text'] = None
if 'show_rewrite' not in st.session_state:
    st.session_state['show_rewrite'] = False
if 'processing_rewrite' not in st.session_state:
    st.session_state['processing_rewrite'] = False
if 'transcription' not in st.session_state:
    st.session_state['transcription'] = None
if 'rewritten_text' not in st.session_state:
    st.session_state['rewritten_text'] = None
if 'show_rewrite' not in st.session_state:
    st.session_state['show_rewrite'] = False
if 'processing_rewrite' not in st.session_state:
    st.session_state['processing_rewrite'] = False
if 'last_error' not in st.session_state:
    st.session_state['last_error'] = None

# Configuración de credenciales de AWS
def get_aws_clients():
    """Configura y retorna los clientes de AWS necesarios"""
    try:
        # Asegurarse de que las credenciales no tengan espacios en blanco
        aws_access_key = st.secrets["AWS_ACCESS_KEY_ID"].strip()
        aws_secret_key = st.secrets["AWS_SECRET_ACCESS_KEY"].strip()

        # Crear una sesión de AWS con las credenciales limpias
        session = boto3.Session(
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )

        # Configurar los clientes con la sesión
        s3_client = session.client('s3')
        transcribe_client = session.client('transcribe')

        # Verificar las credenciales intentando una operación simple
        try:
            s3_client.list_buckets()
        except Exception as e:
            st.error(f"Error de autenticación con AWS: {str(e)}")
            return None, None

        return s3_client, transcribe_client
    except Exception as e:
        st.error(f"Error al configurar los clientes de AWS: {str(e)}")
        return None, None

def on_modify_text_click():
    st.session_state['show_rewrite'] = True
    st.session_state['processing_rewrite'] = True

# Configuración de Anthropic (Claude)
def get_anthropic_client():
    """Configura y retorna el cliente de Anthropic"""
    try:
        return Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception as e:
        st.error(f"Error al configurar el cliente de Anthropic: {str(e)}")
        return None


def generate_unique_filename(original_filename):
    """Genera un nombre de archivo único para S3"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    extension = os.path.splitext(original_filename)[1]
    return f"videos/{timestamp}_{unique_id}{extension}"


def check_file_exists_in_s3(filename):
    """Verifica si un archivo existe en S3 y retorna su URI si existe"""
    s3_client, _ = get_aws_clients()
    if not s3_client:
        return None

    try:
        bucket_name = st.secrets["S3_BUCKET"]
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='videos/'
        )

        # Actualizar el cache de archivos existentes
        st.session_state['existing_files'] = {
            obj['Key']: f"s3://{bucket_name}/{obj['Key']}"
            for obj in response.get('Contents', [])
        }

        # Buscar por nombre de archivo
        for s3_key, s3_uri in st.session_state['existing_files'].items():
            if filename in s3_key:
                url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=3600
                )
                return s3_uri, url

        return None, None
    except Exception as e:
        st.error(f"Error al verificar archivo en S3: {str(e)}")
        return None, None


def upload_to_s3(video_file):
    """Sube el video a S3 y retorna la URL"""
    s3_client, _ = get_aws_clients()
    if not s3_client:
        return None

    try:
        bucket_name = st.secrets["S3_BUCKET"]
        file_name = generate_unique_filename(video_file.name)

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(video_file.getvalue())
            tmp_file.seek(0)
            s3_client.upload_file(
                tmp_file.name,
                bucket_name,
                file_name,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
        os.unlink(tmp_file.name)

        # Generar URL firmada para acceso temporal
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': file_name},
            ExpiresIn=3600
        )

        return f"s3://{bucket_name}/{file_name}", url
    except Exception as e:
        st.error(f"Error al subir el archivo a S3: {str(e)}")
        return None, None


def start_transcription_job(video_s3_uri):
    """Inicia el trabajo de transcripción con Amazon Transcribe"""
    _, transcribe_client = get_aws_clients()
    if not transcribe_client:
        return None

    try:
        job_name = f"transcription_{int(time.time())}_{str(uuid.uuid4())[:8]}"

        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': video_s3_uri},
            MediaFormat='mp4',
            LanguageCode='es-ES',
            Settings={
                'ShowSpeakerLabels': True,
                'MaxSpeakerLabels': 2,
                'ShowAlternatives': False
            }
        )
        return job_name
    except Exception as e:
        st.error(f"Error al iniciar la transcripción: {str(e)}")
        return None


def get_transcription_status(job_name):
    """Verifica el estado del trabajo de transcripción"""
    _, transcribe_client = get_aws_clients()
    if not transcribe_client:
        return None

    try:
        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )
        return response['TranscriptionJob']
    except Exception as e:
        st.error(f"Error al obtener el estado de la transcripción: {str(e)}")
        return None


def get_transcription_text(transcript_uri):
    """Obtiene y procesa el texto transcrito"""
    try:
        response = requests.get(transcript_uri)
        if response.status_code == 200:
            data = response.json()
            return data['results']['transcripts'][0]['transcript']
        return None
    except Exception as e:
        st.error(f"Error al obtener la transcripción: {str(e)}")
        return None


def rewrite_text_with_claude(text):
    """Usa Claude para reescribir el texto evitando detección de plagio"""
    try:
        # Verificar que hay texto para procesar
        if not text or len(text.strip()) < 10:
            st.error("El texto es demasiado corto o está vacío para ser reprocesado.")
            return None

        anthropic = get_anthropic_client()
        if not anthropic:
            st.error("No se pudo inicializar el cliente de Anthropic. Verifica tu API key.")
            return None

        # Dividir el texto en chunks si es muy largo
        max_chunk_length = 4000
        text_chunks = [text[i:i + max_chunk_length] for i in range(0, len(text), max_chunk_length)]
        rewritten_chunks = []

        for i, chunk in enumerate(text_chunks):
            st.write(f"Procesando parte {i + 1} de {len(text_chunks)}...")

            try:
                message = anthropic.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    temperature=0.7,
                    system="Tu tarea es reescribir texto manteniendo el significado exacto. No debes agregar ni quitar información.",
                    messages=[{
                        "role": "user",
                        "content": (
                            "Reescribe cada oracion del siguiente texto con otras palabras, "
                            "manteniendo el significado, mensaje y no alterando la informacion presentada. "
                            "usa entre 650 y 700 palabras. "
                            "Responde unicamente con el texto reescrito siguiendo las indicaciones.\n\n"
                            f"{chunk}"
                        )
                    }]
                )

                # Obtener el contenido del mensaje
                if message and message.content:
                    # Extraer solo el texto de la respuesta
                    content = message.content[0].text

                    # Eliminar cualquier prefacio o texto adicional que Claude pueda agregar
                    # Buscar patrones comunes que Claude agrega y eliminarlos
                    content = content.replace("Aquí está el texto reescrito:", "")
                    content = content.replace("Aquí está la versión reescrita:", "")
                    content = content.replace("Texto reescrito:", "")
                    content = content.strip()

                    rewritten_chunks.append(content)
                else:
                    raise Exception("No se recibió contenido válido de Claude")

            except Exception as chunk_error:
                st.error(f"Error al procesar parte {i + 1}: {str(chunk_error)}")
                return None

        # Unir todos los chunks procesados
        final_text = "\n\n".join(rewritten_chunks)

        # Verificar el resultado final
        if not final_text or len(final_text.strip()) < 10:
            st.error("El texto reprocesado está vacío o es demasiado corto.")
            return None

        return final_text

    except Exception as e:
        st.error(f"Error general al procesar con Claude: {str(e)}")
        return None

def display_status_message(message, type="info"):
    """Muestra mensajes de estado con formato"""
    if type == "info":
        st.info(message)
    elif type == "success":
        st.success(message)
    elif type == "error":
        st.error(message)
    elif type == "warning":
        st.warning(message)


# Interfaz principal de Streamlit
st.title("📹 Procesador de Videos y Transcripciones")
st.markdown("---")

# Área de carga de video
st.subheader("1. Selección y Carga de Video")
video_file = st.file_uploader(
    "Selecciona un video MP4",
    type=['mp4'],
    help="Solo se aceptan archivos en formato MP4"
)

if video_file:

    video_s3_uri, video_url = check_file_exists_in_s3(video_file.name)

    if video_s3_uri:
        st.info("Este archivo ya existe en S3. Usando la versión existente.")
        st.session_state['video_url'] = video_url
        st.session_state['video_s3_uri'] = video_s3_uri

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Iniciar Procesamiento", key="start_processing"):
            st.session_state['processing_failed'] = False

            # Si el archivo no existe en S3, subirlo
            if not video_s3_uri:
                with st.spinner("Subiendo video a AWS..."):
                    video_s3_uri, video_url = upload_to_s3(video_file)
                    if video_s3_uri:
                        st.session_state['video_url'] = video_url
                        st.session_state['video_s3_uri'] = video_s3_uri
                        display_status_message("✅ Video subido exitosamente", "success")

            # Iniciar transcripción
            with st.spinner("Iniciando transcripción..."):
                job_name = start_transcription_job(st.session_state['video_s3_uri'])
                if job_name:
                    st.session_state['job_name'] = job_name
                    display_status_message(
                        "🎯 Transcripción iniciada. Usa el botón 'Verificar Estado' para ver el progreso.",
                        "success"
                    )
                else:
                    st.session_state['processing_failed'] = True
                    display_status_message(
                        "❌ Error al iniciar la transcripción. Puedes intentar nuevamente sin necesidad de volver a subir el video.",
                        "error"
                    )

    with col2:
        # Botón de reintento que aparece solo si hubo un error y el video ya está en S3
        if st.session_state['processing_failed'] and st.session_state['video_s3_uri']:
            if st.button("🔄 Reintentar Transcripción", key="retry_processing"):
                with st.spinner("Reiniciando transcripción..."):
                    job_name = start_transcription_job(st.session_state['video_s3_uri'])
                    if job_name:
                        st.session_state['job_name'] = job_name
                        st.session_state['processing_failed'] = False
                        display_status_message(
                            "🎯 Transcripción reiniciada. Usa el botón 'Verificar Estado' para ver el progreso.",
                            "success"
                        )

# Área de estado y resultados
if st.button("🔄 Verificar Estado"):
    job_info = get_transcription_status(st.session_state['job_name'])

    if job_info:
        status = job_info['TranscriptionJobStatus']

        if status == 'COMPLETED':
            transcript_uri = job_info['Transcript']['TranscriptFileUri']
            transcription = get_transcription_text(transcript_uri)

            if transcription:
                st.session_state['transcription'] = transcription

                # Mostrar resultados en dos columnas
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Video Original")
                    st.video(st.session_state['video_url'])

                with col2:
                    st.subheader("Transcripción")
                    st.text_area(
                        "Texto transcrito",
                        transcription,
                        height=300,
                        key="transcription_area"
                    )

                    st.download_button(
                        label="📥 Descargar Transcripción",
                        data=transcription,
                        file_name="transcripcion.txt",
                        mime="text/plain",
                        key="download_transcription"
                    )

                # Botón para mostrar sección de reprocesamiento
                st.button("🔄 Modificar Texto", on_click=on_modify_text_click)

# Sección de reprocesamiento (se muestra solo cuando show_rewrite es True)
if st.session_state.get('show_rewrite', False):
    st.markdown("---")
    st.subheader("3. Reprocesamiento de Texto")

    # Solo procesar si aún no se ha hecho
    if st.session_state.get('processing_rewrite', False):
        with st.spinner("Analizando texto para reprocesamiento..."):
            transcription = st.session_state['transcription']

            if not transcription or len(transcription.strip()) < 10:
                st.error("No hay suficiente texto para reprocesar.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("Iniciando reprocesamiento con Claude...")
                progress_bar.progress(25)

                rewritten_text = rewrite_text_with_claude(transcription)

                if rewritten_text:
                    st.session_state['rewritten_text'] = rewritten_text
                    st.session_state['processing_rewrite'] = False  # Marcar como procesado
                    progress_bar.progress(100)
                    status_text.text("¡Reprocesamiento completado!")
                else:
                    progress_bar.progress(100)
                    st.error("No se pudo completar el reprocesamiento.")
                    # Agregar botón de reintento
                    if st.button("🔄 Reintentar Procesamiento"):
                        st.session_state['processing_rewrite'] = True
                        st.experimental_rerun()

    # Mostrar resultados del reprocesamiento si existen
    if st.session_state.get('rewritten_text'):
        st.text_area(
            f"Texto Reprocesado ({len(st.session_state['rewritten_text'].split())} palabras)",
            st.session_state['rewritten_text'],
            height=300,
            key="rewritten_area"
        )

        st.download_button(
            label="📥 Descargar Texto Reprocesado",
            data=st.session_state['rewritten_text'],
            file_name="texto_reprocesado.txt",
            mime="text/plain",
            key="download_rewritten"
        )

# Instrucciones en la barra lateral
with st.sidebar:
    st.header("📋 Instrucciones")
    st.markdown("""
    1. **Carga del Video**
       * Selecciona un archivo MP4
       * Haz clic en "Iniciar Procesamiento"

    2. **Transcripción**
       * Espera a que se complete el proceso
       * Usa "Verificar Estado" para ver el progreso

    3. **Resultados**
       * Revisa la transcripción
       * Descarga el texto si lo deseas

    4. **Modificar Texto**
       * Usa Claude para reescribir el texto
       * Descarga la versión reprocesada
    """)

    st.markdown("---")
    st.markdown("### 🔧 Requerimientos")
    st.markdown("""
    * Archivo de video en formato MP4
    * Conexión estable a internet
    * El video debe tener audio claro
    """)