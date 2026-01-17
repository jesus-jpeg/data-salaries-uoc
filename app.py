import streamlit as st
import re
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy import create_engine, text

# =====================
# CONFIGURACIÓN STREAMLIT
# =====================
st.set_page_config(
    page_title="UOC · Registro",
    page_icon="🎓",
    layout="centered",
)

# =====================
# ESTILOS UOC
# =====================
UOC_BG = "#73EDFF"
UOC_TEXT = "#000078"

uoc_css = f"""
<style>
/* Fondo general */
.stApp {{
    background: {UOC_BG};
    color: {UOC_TEXT};
}}

/* Títulos y texto */
h1, h2, h3, h4, h5, h6, p, label, span, div {{
    color: {UOC_TEXT} !important;
}}

/* Inputs */
.stTextInput input, .stNumberInput input, .stDateInput input {{
    background: #ffffff !important;
    color: {UOC_TEXT} !important;
    border: 1px solid {UOC_TEXT}33 !important;
    border-radius: 10px !important;
}}

.stSelectbox div[data-baseweb="select"] > div {{
    background: #ffffff !important;
    color: {UOC_TEXT} !important;
    border: 1px solid {UOC_TEXT}33 !important;
    border-radius: 10px !important;
}}

/* Checkbox */
.stCheckbox label {{
    color: {UOC_TEXT} !important;
}}

/* Botón */
.stButton button, .stFormSubmitButton button {{
    background: {UOC_TEXT} !important;
    color: #ffffff !important;
    border-radius: 12px !important;
    border: none !important;
    padding: 0.6rem 1rem !important;
    font-weight: 700 !important;
}}
.stButton button:hover, .stFormSubmitButton button:hover {{
    opacity: 0.92 !important;
}}

/* Ocultar menú */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}
</style>
"""
st.markdown(uoc_css, unsafe_allow_html=True)

# =====================
# CONEXIÓN A RDS (MySQL)
# =====================
@st.cache_resource(show_spinner=False)
def get_engine():
    return create_engine(
        st.secrets["db"]["url"],
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        future=True
    )

engine = get_engine()

# =====================
# CATÁLOGOS
# =====================
PAISES = [
    "España", "México", "Argentina", "Colombia", "Chile", "Perú",
    "Estados Unidos", "Portugal", "Reino Unido", "Alemania", "Francia", "Otro"
]

CIUDADES_POR_PAIS = {
    "España": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Otro"],
    "México": ["Ciudad de México", "Guadalajara", "Monterrey", "Otro"],
    "Argentina": ["Buenos Aires", "Córdoba", "Rosario", "Otro"],
    "Colombia": ["Bogotá", "Medellín", "Cali", "Otro"],
    "Chile": ["Santiago", "Valparaíso", "Concepción", "Otro"],
    "Perú": ["Lima", "Arequipa", "Trujillo", "Otro"],
    "Estados Unidos": ["New York", "San Francisco", "Los Angeles", "San Diego", "Otro"],
    "Portugal": ["Lisboa", "Oporto", "Otro"],
    "Reino Unido": ["Londres", "Manchester", "Edimburgo", "Otro"],
    "Alemania": ["Berlín", "Múnich", "Hamburgo", "Otro"],
    "Francia": ["París", "Lyon", "Marsella", "Otro"],
    "Otro": ["Otro"]
}

EXPERIENCIAS = ["Intern","Junior", "Mid", "Senior", "Expert"]
POSICIONES = ["Data Scientist", "Data Engineer", "Machine Learning Engineer", "Data Analyst", "Business Intelligence Analyst", "AI Engineer"]

# =====================
# FUNCIONES
# =====================
EMAIL_REGEX = re.compile(
    r"^(?=.{3,254}$)[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)

def validate_email(email: str) -> bool:
    return bool(email) and EMAIL_REGEX.match(email) is not None

def generate_unique_id() -> str:
    return str(uuid.uuid4())

def parse_salario(value: str) -> Decimal | None:
    if value is None:
        return None
    raw = value.strip()
    if raw == "":
        return None

    normalized = raw.replace(" ", "").replace(",", ".")
    for sym in ["€", "$", "USD", "EUR"]:
        normalized = normalized.replace(sym, "")

    try:
        dec = Decimal(normalized)
        if dec < 0:
            return None
        return dec.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

def save_contact(
    uid: str,
    nombre: str,
    email: str,
    fecha_nacimiento,
    salario_bruto: Decimal | None,
    pais: str,
    ciudad: str,
    experiencia: str,
    empresa: str,
    posicion: str,
    consent_accepted: bool,
    consent_ts,
    created_ts
):
    """
    Upsert por email. Requiere UNIQUE(email).
    OJO: la tabla debe tener columnas: empresa, posicion, experiencia.
    """
    sql = """
    INSERT INTO salaries (
        id, nombre, email, fecha_nacimiento,
        salario_bruto, pais, ciudad,
        experiencia, empresa, posicion,
        consent_accepted, consent_ts,
        created_at, updated_at
    )
    VALUES (
        :id, :nombre, :email, :fecha_nacimiento,
        :salario_bruto, :pais, :ciudad,
        :experiencia, :empresa, :posicion,
        :consent_accepted, :consent_ts,
        :created_at, :updated_at
    )
    ON DUPLICATE KEY UPDATE
        nombre = VALUES(nombre),
        fecha_nacimiento = VALUES(fecha_nacimiento),
        salario_bruto = VALUES(salario_bruto),
        pais = VALUES(pais),
        ciudad = VALUES(ciudad),
        experiencia = VALUES(experiencia),
        empresa = VALUES(empresa),
        posicion = VALUES(posicion),
        consent_accepted = VALUES(consent_accepted),
        consent_ts = VALUES(consent_ts),
        updated_at = VALUES(updated_at);
    """
    with engine.begin() as conn:
        conn.execute(
            text(sql),
            {
                "id": uid,
                "nombre": nombre,
                "email": email,
                "fecha_nacimiento": fecha_nacimiento,
                "salario_bruto": float(salario_bruto) if salario_bruto is not None else None,
                "pais": pais,
                "ciudad": ciudad,
                "experiencia": experiencia,
                "empresa": empresa,
                "posicion": posicion,
                "consent_accepted": 1 if consent_accepted else 0,
                "consent_ts": consent_ts,
                "created_at": created_ts,
                "updated_at": created_ts,
            }
        )

# =====================
# FRONT
# =====================
st.write("##")
st.title("Formulario de registro (UOC)")

c1, c2 = st.columns(2, gap="large")

with c1:
    st.write("##")
    st.image("assets/logo.png", caption="UOC Style", use_container_width=True)

with c2:
    st.write("##")
    with st.form("contact_form", clear_on_submit=False):
        nombre = st.text_input("Nombre*", placeholder="Tu nombre")
        email = st.text_input("Email*", placeholder="Tu mejor email")

        fecha_nacimiento = st.date_input(
            "Fecha de nacimiento",
            value=None,
            format="DD/MM/YYYY"
        )

        salario_str = st.text_input(
            "Salario bruto anual (€)*",
            placeholder="Ej: 35000 o 35000,00"
       	)

        pais = st.selectbox("País*", options=PAISES, key="pais")
        ciudades_disp = CIUDADES_POR_PAIS.get(pais, ["Otro"])
        if st.session_state.get("ciudad") not in ciudades_disp:
            st.session_state["ciudad"] = ciudades_disp[0]
        ciudad = st.selectbox("Ciudad*", options=ciudades_disp, key="ciudad")

        experiencia = st.selectbox("Experiencia*", options=EXPERIENCIAS, index=0)

        empresa = st.text_input("Empresa*", placeholder="Nombre de la empresa")
        posicion = st.selectbox("Posición*", options=POSICIONES, index=0)

        policy = st.checkbox("Acepto recibir comunicaciones y la política de privacidad")

        enviar = st.form_submit_button("Enviar")

    if enviar:
        nombre_norm = (nombre or "").strip()
        email_norm = (email or "").strip().lower()
        empresa_norm = (empresa or "").strip()
        salario_dec = parse_salario(salario_str)

        if not nombre_norm:
            st.error("Por favor, completa el campo del nombre")
        elif not email_norm:
            st.error("Por favor, completa el campo del email")
        elif not validate_email(email_norm):
            st.error("Por favor, ingresa un email válido")
        elif fecha_nacimiento is not None and fecha_nacimiento > date.today():
            st.error("Por favor, ingresa una fecha de nacimiento válida")
        elif salario_dec is None:
            st.error("Por favor, ingresa un salario bruto válido (número positivo)")
        elif not pais:
            st.error("Por favor, selecciona un país")
        elif not ciudad:
            st.error("Por favor, selecciona una ciudad")
        elif experiencia not in EXPERIENCIAS:
            st.error("Por favor, selecciona una experiencia válida")
        elif not empresa_norm:
            st.error("Por favor, completa el campo empresa")
        elif posicion not in POSICIONES:
            st.error("Por favor, selecciona una posición válida")
        elif not policy:
            st.error("Por favor, acepta la política de privacidad")
        else:
            if st.session_state.get("submitting", False):
                st.info("Procesando tu solicitud, por favor espera…")
            else:
                st.session_state.submitting = True
                try:
                    with st.spinner("Guardando información…"):
                        uid = generate_unique_id()
                        now_utc = datetime.now(timezone.utc)

                        save_contact(
                            uid=uid,
                            nombre=nombre_norm,
                            email=email_norm,
                            fecha_nacimiento=fecha_nacimiento,
                            salario_bruto=salario_dec,
                            pais=pais,
                            ciudad=ciudad,
                            experiencia=experiencia,
                            empresa=empresa_norm,
                            posicion=posicion,
                            consent_accepted=True,
                            consent_ts=now_utc,
                            created_ts=now_utc
                        )

                    st.success("✅ Datos guardados correctamente")
                except Exception as e:
                    st.error("Ha ocurrido un error al guardar tus datos.")
                    st.exception(e)
                finally:
                    st.session_state.submitting = False

st.write("##")
st.caption("© 2026 UOC Salaries · Todos los derechos reservados")
