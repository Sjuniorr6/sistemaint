from pathlib import Path
import os.path
import os
import json
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-88)5ylc$&!#l7%0$oq&bdfn$*gzc#!-sk+*yj(216bb7-aq%y2'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', 'intgoldensat.com.br', 'www.intgoldensat.com.br', 'testserver']
AGENTTRACKER_WEB_BASE_URL = "https://intgoldensat.com.br"


# GS_ACIONAMENTO_URL = 'http://127.0.0.1:8000'
# GS_ACIONAMENTO_TOKEN = '9c50d06c647e4ca8609ca1bf0ecfde5ee74b2c88'
GS_ACIONAMENTO_URL = 'https://gsacionamento.com/'
GS_ACIONAMENTO_TOKEN = '3c291aec7e1673aa2263070a6f57fae7896332b0'

#LOGGING = {
 #  'version': 1,


ROLESPERMISSIONS_MODULE = 'app.roles'


CSRF_TRUSTED_ORIGINS = [
    'https://intgoldensat.com.br',
    'https://www.intgoldensat.com.br',
    'http://127.0.0.1:8000',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'adm',
    'cliente',
    'produto',
    'register',
    'acompanhamento',
    'tuper',
    'faturamento',
    'home',
    'rolepermissions',
    'login',
    'requisicao',
    'manutencaolist',
    'reativacao',
    'qualit',
    'formulariov',
    'formularioe',
    'usuarios',     
    'estoque',     
    'registrodemanutencao',
    'saidas',
    'formacompanhamento',    
    'prestadores',    
    'regcliente',    
    'dashboard',    
    'IAO',   
    't42', 
    'pparada', 
    'ticket',
    'projetos',
    'horas', 
    'goldenx',    
    'documentacoes',
    'Nestle',  
    'corte',
    'compras',
    'franquia',
    # 'acompanhamentos',
    'kanban_inteligencia',
    'kanban_TI',
    "acompanhamentos.apps.AcompanhamentosConfig",
    'kanban_marketing',
    'controle_administrativo',
    'django_celery_beat',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'app.middleware.NoIndexMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Adicione este middleware
]

# OpenStreetMap tile servers require Referer for usage-policy compliance.
# Django default "same-origin" strips referrer on cross-origin tile requests.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = 'app.urls'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}




TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Atualizado para pasta templates na raiz
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'registrodemanutencao.context_processors.manutencoes_pendentes',
            ],
        },
    },
]


# Permitir o domínio da plataforma T42
CSRF_TRUSTED_ORIGINS = [
    'https://intgoldensat.com.br',
    'https://www.intgoldensat.com.br',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# Se usar autenticação via token (DRF)
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Métodos HTTP permitidos
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Permitir credenciais (cookies, autenticação)
CORS_ALLOW_CREDENTIALS = True

WSGI_APPLICATION = 'app.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
LOGOUT_REDIRECT_URL ="/"

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Pasta onde seus arquivos estáticos residem durante o desenvolvimento
    os.path.join(BASE_DIR, 'app', 'static'),  # Pasta static dentro de app
    os.path.join(BASE_DIR, 'public'),
]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Configuração de email para envio real
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATE_INPUT_FORMATS = ['%d/%m/%Y']
DATE_FORMAT = 'd/m/Y'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = 'sysggoldensat@gmail.com'
EMAIL_HOST_PASSWORD = 'yzxs ieko subp xesu'  # Senha de app do Gmail
DEFAULT_FROM_EMAIL = 'sysggoldensat@gmail.com'

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ODOMETER_MODEL = os.getenv("OPENAI_ODOMETER_MODEL", "")
ODOMETER_AI_MODEL = os.getenv("ODOMETER_AI_MODEL", OPENAI_ODOMETER_MODEL or "gpt-4o-mini")

# Google Maps / Routes API
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# AssetsControls (Nestle battery lookup for prefixes 8373/8375/8303/8304)
# ASSETSCONTROLS_FGUIDS: comma-separated GUID list accepted by QueryLBSMonitorListByFGUIDs
_assetscontrols_seed_path = BASE_DIR / "Nestle" / "assetscontrols_fguids_seed.txt"
if _assetscontrols_seed_path.exists():
    _assetscontrols_seed_fguids = _assetscontrols_seed_path.read_text(encoding="utf-8").strip()
else:
    _assetscontrols_seed_fguids = ""

ASSETSCONTROLS_FGUIDS = os.getenv("ASSETSCONTROLS_FGUIDS", _assetscontrols_seed_fguids)

# ASSETSCONTROLS_GUID_BY_ASSET: JSON map {"837303000460": "5F94..."}
try:
    ASSETSCONTROLS_GUID_BY_ASSET = json.loads(os.getenv("ASSETSCONTROLS_GUID_BY_ASSET", "{}"))
except json.JSONDecodeError:
    ASSETSCONTROLS_GUID_BY_ASSET = {}

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "mission_evidence")
SUPABASE_WEBHOOK_SECRET = os.getenv("SUPABASE_WEBHOOK_SECRET", "").strip()

MISSION_PHOTOS_TMP_DIR = os.getenv("MISSION_PHOTOS_TMP_DIR", "static/tmp_mission_photos")
MISSION_PHOTOS_TMP_ABS = os.path.join(BASE_DIR, MISSION_PHOTOS_TMP_DIR)
os.makedirs(MISSION_PHOTOS_TMP_ABS, exist_ok=True)

LOGIN_REDIRECT_URL = 'home'  # Nome da URL para redirecionar após login
LOGOUT_REDIRECT_URL = 'login'  # Nome da URL para redirecionar após logout
LOGIN_URL = 'login'
# Verifique se 'login' está corretamente configurado e inclui a URL para login.
ROLESPERMISSIONS_MODULE = 'app.roles'  # Certifique-se de que o caminho está correto


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_decimal(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(Decimal(raw))
    except (TypeError, InvalidOperation, ValueError):
        return float(default)


# Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TIME_LIMIT = _env_int("CELERY_TASK_TIME_LIMIT", 120)
CELERY_TASK_SOFT_TIME_LIMIT = _env_int("CELERY_TASK_SOFT_TIME_LIMIT", 90)
CELERY_WORKER_PREFETCH_MULTIPLIER = _env_int("CELERY_WORKER_PREFETCH_MULTIPLIER", 1)
CELERY_TASK_ACKS_LATE = os.getenv("CELERY_TASK_ACKS_LATE", "true").lower() == "true"
CELERY_TIMEZONE = os.getenv("CELERY_TIMEZONE", "America/Sao_Paulo")
CELERY_TASK_DEFAULT_QUEUE = "monitoramento.orquestrador"
CELERY_TASK_ROUTES = {
    "acompanhamentos.tasks.processar_foto_task": {"queue": "monitoramento.photos"},
    "acompanhamentos.tasks.processar_fotos_pendentes_task": {"queue": "monitoramento.photos"},
    "acompanhamentos.tasks.processar_geofence_task": {"queue": "monitoramento.geofence"},
    "acompanhamentos.tasks.ciclo_monitoramento_task": {"queue": "monitoramento.orquestrador"},
}
CELERY_BEAT_SCHEDULE = {
    "ciclo-monitoramento": {
        "task": "acompanhamentos.tasks.ciclo_monitoramento_task",
        "schedule": _env_decimal("CELERY_MONITORAMENTO_INTERVAL_SECONDS", "15"),
        "options": {"queue": "monitoramento.orquestrador"},
    },
}

# Mission photos / IA de odometro
MISSION_PHOTO_PROCESSING_LOCK_TTL_SECONDS = _env_int("MISSION_PHOTO_PROCESSING_LOCK_TTL_SECONDS", 120)
MISSION_PHOTO_QUEUE_DISPATCH_TIMEOUT_SECONDS = _env_decimal("MISSION_PHOTO_QUEUE_DISPATCH_TIMEOUT_SECONDS", "2.0")
ODOMETER_AI_TIMEOUT_SECONDS = _env_decimal("ODOMETER_AI_TIMEOUT_SECONDS", "30")
ODOMETER_AI_MAX_RETRIES = _env_int("ODOMETER_AI_MAX_RETRIES", 0)
