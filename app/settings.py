from pathlib import Path
import os.path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-88)5ylc$&!#l7%0$oq&bdfn$*gzc#!-sk+*yj(216bb7-aq%y2'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', 'intgoldensat.com.br', 'www.intgoldensat.com.br']


#LOGGING = {
 #  'version': 1,
  #  'disable_existing_loggers': False,
   # 'handlers': {
   #     'file': {
   #         'level': 'DEBUG',
   #         'class': 'logging.FileHandler',
   #         'filename': 'debug.log',
   #     },
   # },
   # 'loggers': {
   #     'django': {
   #         'handlers': ['file'],
   #         'level': 'DEBUG',
   #         'propagate': True,
   #     },
   # },
#}

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
    'kanban_inteligencia',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    # Adicione este middleware
]

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
            ],
        },
    },
]



# Permitir o domínio da plataforma T42
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",  # ou domínio real da plataforma T42
    
]

# Se usar autenticação via token (DRF)
CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
]

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
USE_TZ = False

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Pasta onde seus arquivos estáticos residem durante o desenvolvimento
    os.path.join(BASE_DIR, 'app', 'static'),  # Pasta static dentro de app
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

LOGIN_REDIRECT_URL = 'home'  # Nome da URL para redirecionar após login
LOGOUT_REDIRECT_URL = 'login'  # Nome da URL para redirecionar após logout
LOGIN_URL = 'login'
# Verifique se 'login' está corretamente configurado e inclui a URL para login.
ROLESPERMISSIONS_MODULE = 'app.roles'  # Certifique-se de que o caminho está correto
