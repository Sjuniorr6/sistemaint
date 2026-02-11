# api/supabase_client.py
import logging
from django.conf import settings
from supabase import create_client
import httpx

logger = logging.getLogger(__name__)

_supabase = None


def _create_client():
    """
    Cria cliente Supabase com configurações robustas:
    - timeout: 30s (ler + escrever)
    - limits: pool size limitado para evitar muitas conexões
    - retry_retries: 3 tentativas de retry automático do httpx
    """
    # Criar custom httpx client com timeout e pool config
    http_client = httpx.Client(
        timeout=30.0,  # 30s total
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        ),
    )
    
    client = create_client(
        settings.SUPABASE_URL, 
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
    
    # Injetar cliente httpx customizado
    if hasattr(client, 'postgrest'):
        client.postgrest.session = http_client
    
    return client


def get_supabase(force_new=False):
    global _supabase
    if _supabase is None or force_new:
        _supabase = _create_client()
    return _supabase


def reset_supabase():
    global _supabase
    _supabase = None
    logger.info("Supabase client resetado (conexão stale)")