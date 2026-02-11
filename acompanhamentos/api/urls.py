from django.urls import path
from . import views
from . import views_supabase_read as v
from . import views_supabase_photos_process as vp
from . import views_supabase_mission_ops as ops

urlpatterns = [
    # ══════════════════════════════════════════════════════
    # ENDPOINTS LEGADOS (Django direto)
    # ══════════════════════════════════════════════════════
    path("missao/<str:id>/", views.api_missao_detail, name="api_missao_detail"),
    path("missao/<str:id>/location/", views.api_missao_location, name="api_missao_location"),
    path("missao/<str:id>/panic/", views.api_missao_panic, name="api_missao_panic"),
    path("missao/<str:id>/localizacoes/", views.api_missao_localizacoes, name="api_missao_localizacoes"),
    path("missao/<str:id>/wait-panic/", views.api_missao_wait_panic, name="api_missao_wait_panic"),
    path("localizacao/<int:localizacao_id>/resolver-panico/", views.api_resolver_panico, name="api_resolver_panico"),
    path("missao/<str:id>/panic-status/", views.api_missao_panic_status, name="api_missao_panic_status"),

    # ══════════════════════════════════════════════════════
    # LEITURA SUPABASE (já existentes)
    # ══════════════════════════════════════════════════════
    path("supabase/missions_control/", v.sb_missions_control_list, name="sb_missions_control_list"),
    path("supabase/mission_tracking/", v.sb_mission_tracking_list, name="sb_mission_tracking_list"),
    path("supabase/mission_photos/", v.sb_mission_photos_list, name="sb_mission_photos_list"),
    path("supabase/full/", v.sb_mission_full, name="sb_mission_full"),
    path("supabase/panic_alerts/", v.sb_panic_alerts_list, name="sb_panic_alerts_list"),
    path("supabase/panic_alerts/<str:panic_id>/ack/", v.sb_panic_ack, name="sb_panic_ack"),

    # PROCESSAR FOTO (odômetro IA)
    path("supabase/mission_photos/<str:photo_id>/process/", vp.sb_process_one_photo, name="sb_process_one_photo"),

    # ✅ NOVO: fallback para processar fotos pendentes (DEV/local + redundância)
    path("supabase/mission_photos/process-pending/", vp.sb_process_pending_photos, name="sb_process_pending_photos"),

    # ══════════════════════════════════════════════════════
    # OPERAÇÕES DE MISSÃO (CICLO DE VIDA) — NOVOS
    # ══════════════════════════════════════════════════════

    # 1) Aceitar missão: pendente → missao_aceita
    path(
        "supabase/mission/<str:mission_id>/accept/",
        ops.sb_mission_accept,
        name="sb_mission_accept",
    ),

    # 2) Enviar localização (tracking a cada 30s)
    path(
        "supabase/mission/<str:mission_id>/location/",
        ops.sb_mission_location,
        name="sb_mission_location",
    ),

    # 3) Pânico-teste: odometro_inicio_verificado → teste_panico
    path(
        "supabase/mission/<str:mission_id>/panic-test/",
        ops.sb_mission_panic_test,
        name="sb_mission_panic_test",
    ),

    # 4) Resolver pânico-teste: teste_panico → teste_panico_verificado
    path(
        "supabase/mission/<str:mission_id>/panic-resolve/",
        ops.sb_mission_panic_resolve,
        name="sb_mission_panic_resolve",
    ),

    # 5) Iniciar missão: teste_panico_verificado → em_andamento
    path(
        "supabase/mission/<str:mission_id>/start/",
        ops.sb_mission_start,
        name="sb_mission_start",
    ),

    # 6) Pânico real (durante em_andamento, não muda status)
    path(
        "supabase/mission/<str:mission_id>/panic/",
        ops.sb_mission_panic_real,
        name="sb_mission_panic_real",
    ),

    # 7) Concluir missão: odometro_final_verificado → concluido
    path(
        "supabase/mission/<str:mission_id>/finish/",
        ops.sb_mission_finish,
        name="sb_mission_finish",
    ),

    # 8) Status completo (GET — para polling do mapa)
    path(
        "supabase/mission/<str:mission_id>/status/",
        ops.sb_mission_status,
        name="sb_mission_status",
    ),

    path(
        "supabase/mission/<str:mission_id>/geofence-check/",
        ops.sb_mission_geofence_check,
        name="sb_mission_geofence_check",
    ),

    # WEBHOOK
    path('webhooks/mission-photo/', views.mission_photo_webhook, name='mission_photo_webhook'),
]