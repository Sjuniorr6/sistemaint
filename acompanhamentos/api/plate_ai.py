# api/plate_ai.py
import base64
import io
import json
import re
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

# OpenCV é opcional (melhora cálculo de blur e crop). Se não tiver, usa fallback.
try:
    import cv2
except Exception:
    cv2 = None

from openai import OpenAI


# ======================================================
# CONFIGS DE VALIDAÇÃO
# ======================================================

MIN_CONFIDENCE = 0.70
MIN_WIDTH = 600
MIN_HEIGHT = 600
BLUR_THRESHOLD = 20.0  # Reduzido para aceitar mais fotos (apenas extremamente borradas serão rejeitadas)

# Padrão brasileiro de placas: ABC1234 (Mercosul: ABC1D23)
PLATE_PATTERN_OLD = r'^[A-Z]{3}\d{4}$'  # Padrão antigo: ABC1234
PLATE_PATTERN_MERCOSUL = r'^[A-Z]{3}\d[A-Z]\d{2}$'  # Padrão Mercosul: ABC1D23

# ======================================================
# DEBUG MODE - SALVA IMAGENS E LOGS
# ======================================================
# 
# Quando DEBUG_MODE = True, o sistema salva em static/plate_debug/:
#   - {timestamp}_01_original.jpg      → Imagem original recebida (ENVIADA PARA IA)
#   - {timestamp}_02_processed.jpg     → Igual à original (sem processamento)
#   - {timestamp}_03_crop.jpg          → Crop da placa (se detectado, SEM processamento)
#   - {timestamp}_request_log.json     → Detalhes da requisição à OpenAI
#   - {timestamp}_response_log.json    → Metadados da resposta (tokens, modelo, etc)
#   - {timestamp}_raw_response.txt     → Texto RAW retornado pela IA (IMPORTANTE!)
#   - {timestamp}_info_log.json        → Info geral (tamanho, issues, etc)
#
# NOTA: Removido pré-processamento (sharpen/contraste) - a imagem original é melhor!
#
# Para acessar os arquivos de debug:
#   - Local: http://localhost:8000/static/plate_debug/
#   - Produção: https://intgoldensat.com.br/static/plate_debug/
#
DEBUG_MODE = False  # Mude para False em produção
DEBUG_DIR = os.path.join(settings.BASE_DIR, "static", "plate_debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================

def _img_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Converte bytes em PIL Image RGB aplicando rotação EXIF correta."""
    img = Image.open(io.BytesIO(image_bytes))
    
    # Aplica rotação baseada em EXIF (corrige orientação da câmera)
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        # Se falhar, continua com a imagem original
        pass
    
    return img.convert("RGB")


def _estimate_blur_score(pil_img: Image.Image) -> float:
    """Estima blur score usando Laplacian variance ou fallback."""
    img = np.array(pil_img)

    if img.shape[1] > 1600:
        scale = 1600 / img.shape[1]
        new_w = 1600
        new_h = int(img.shape[0] * scale)
        pil_resized = pil_img.resize((new_w, new_h))
        img = np.array(pil_resized)

    if cv2 is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        return float(lap.var())

    gray = img.mean(axis=2)
    gx = np.diff(gray, axis=1)
    gy = np.diff(gray, axis=0)
    score = float(np.var(gx) + np.var(gy))
    return score


def _preprocess_image(pil_img: Image.Image) -> Image.Image:
    """Retorna imagem original SEM processamento - gpt-4o-mini é bom o suficiente."""
    return pil_img


def _to_data_url_from_pil(pil_img: Image.Image) -> str:
    """Converte PIL em data URL base64 (jpeg)."""
    out = io.BytesIO()
    pil_img.save(out, format="JPEG", quality=95, optimize=True)
    b64 = base64.b64encode(out.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _normalize_plate(raw: str) -> str:
    """
    Normaliza a placa removendo espaços, hífens e caracteres especiais.
    Converte para maiúsculas e remove tudo exceto letras e números.
    """
    if not raw:
        return ""
    # Remove espaços, hífens e caracteres especiais
    normalized = re.sub(r'[^A-Z0-9]', '', raw.upper())
    return normalized


def _validate_plate_format(plate: str) -> tuple[bool, str]:
    """
    Valida se a placa está no formato brasileiro correto.
    Retorna: (is_valid, format_type)
    format_type pode ser: 'old', 'mercosul', 'invalid'
    """
    if not plate:
        return False, "invalid"
    
    # Normaliza a placa
    plate_clean = _normalize_plate(plate)
    
    # Verifica padrão Mercosul (ABC1D23)
    if re.match(PLATE_PATTERN_MERCOSUL, plate_clean):
        return True, "mercosul"
    
    # Verifica padrão antigo (ABC1234)
    if re.match(PLATE_PATTERN_OLD, plate_clean):
        return True, "old"
    
    return False, "invalid"


def _basic_sanity_checks(pil_img: Image.Image) -> List[str]:
    """Checagens básicas locais."""
    issues: List[str] = []

    w, h = pil_img.size
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        issues.append(f"image_low_resolution({w}x{h})")

    blur_score = _estimate_blur_score(pil_img)
    if blur_score < BLUR_THRESHOLD:
        issues.append(f"image_blurry(blur_score={blur_score:.1f})")

    return issues


def _debug_save_image(pil_img: Image.Image, label: str, timestamp: str) -> str:
    """Salva imagem para debug com timestamp (mantém orientação correta)."""
    if not DEBUG_MODE:
        return ""
    
    filename = f"{timestamp}_{label}.jpg"
    filepath = os.path.join(DEBUG_DIR, filename)
    # Salva com qualidade alta e sem metadados EXIF (já aplicamos a rotação)
    pil_img.save(filepath, "JPEG", quality=95, exif=b"")
    return filepath


def _debug_log(timestamp: str, data: Dict[str, Any]) -> str:
    """Salva log JSON para debug."""
    if not DEBUG_MODE:
        return ""
    
    filename = f"{timestamp}_log.json"
    filepath = os.path.join(DEBUG_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


# ======================================================
# CROP AUTOMÁTICO DA PLACA (MELHORADO)
# ======================================================

def _auto_crop_plate(pil_img: Image.Image) -> Optional[Image.Image]:
    """
    Tenta localizar a placa do veículo na imagem.
    Busca por regiões retangulares com características de placa.
    """
    arr = np.array(pil_img)

    if cv2 is not None:
        return _auto_crop_plate_cv2(arr, pil_img)
    else:
        # Sem OpenCV, não fazemos crop automático (enviamos imagem completa)
        return None


def _auto_crop_plate_cv2(arr: np.ndarray, pil_img: Image.Image) -> Optional[Image.Image]:
    """
    Crop usando OpenCV - detecta regiões retangulares que podem ser placas.
    Placas brasileiras geralmente são cinzas/brancas com proporção ~2:1 (largura:altura)
    """
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    
    # Aplica threshold adaptativo para destacar regiões claras (placa)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Encontra contornos
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # Procura por contornos retangulares com proporção de placa
    plate_candidates = []
    
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        
        # Regras básicas de tamanho
        if w < 80 or h < 30:
            continue
        
        # Proporção aproximada de placa brasileira (2:1 a 4:1)
        aspect_ratio = w / h if h > 0 else 0
        if not (1.8 <= aspect_ratio <= 5.0):
            continue
        
        # Área mínima
        area = w * h
        if area < 2400:  # ~80x30
            continue
        
        plate_candidates.append((x, y, w, h, area))
    
    if not plate_candidates:
        return None
    
    # Pega o maior candidato (geralmente a placa é uma das maiores regiões retangulares)
    x, y, w, h, _ = max(plate_candidates, key=lambda c: c[4])
    
    # Adiciona margem
    pad_x = int(w * 0.15)
    pad_y = int(h * 0.15)
    x0 = max(x - pad_x, 0)
    y0 = max(y - pad_y, 0)
    x1 = min(x + w + pad_x, pil_img.size[0])
    y1 = min(y + h + pad_y, pil_img.size[1])
    
    cropped = pil_img.crop((x0, y0, x1, y1))
    
    # Verifica se o crop é válido
    cw, ch = cropped.size
    if cw < 60 or ch < 20:
        return None
    
    return cropped


# ======================================================
# CHAMADA À API OPENAI (PROMPT OTIMIZADO PARA PLACAS)
# ======================================================

def _build_prompt() -> str:
    """Prompt otimizado para leitura de placas brasileiras."""
    return """You are analyzing a Brazilian vehicle photo to read the LICENSE PLATE.

CRITICAL RULES:
1. Brazilian license plates have TWO formats:
   - OLD FORMAT: ABC1234 (3 letters + 4 numbers) - Example: ABC1234
   - MERCOSUL FORMAT: ABC1D23 (3 letters + 1 number + 1 letter + 2 numbers) - Example: ABC1D23

2. License plates are usually:
   - GRAY/WHITE background with BLACK text (most common)
   - Rectangular shape with aspect ratio ~2:1 to 4:1
   - Located at the FRONT or REAR of the vehicle

3. Common errors to avoid:
   - Confusing letter O with number 0
   - Confusing letter I with number 1
   - Confusing letter Z with number 2
   - Confusing letter S with number 5
   - Reading partial plates or stickers

STEP-BY-STEP PROCESS:
1. Locate the license plate in the image (front or rear of vehicle)
2. Read the characters carefully from LEFT to RIGHT
3. Verify the format matches Brazilian standards (ABC1234 or ABC1D23)
4. Double-check for common OCR errors (O/0, I/1, Z/2, S/5)

EXAMPLES OF VALID PLATES:
- ABC1234 (old format)
- XYZ9876 (old format)
- ABC1D23 (Mercosul format)
- XYZ9A87 (Mercosul format)

Return ONLY valid JSON:
{
    "plate_number": "<exact plate text>",
    "plate_format": "old or mercosul",
    "confidence": <float 0.0 to 1.0>,
    "plate_color": "gray, white, or other",
    "plate_location": "front or rear",
    "reasoning": "<explain what you see and why you're confident>"
}

If you CANNOT read the plate clearly:
{"plate_number": null, "confidence": 0.0, "reasoning": "<why it failed>"}"""


def _call_openai_vision(data_url: str, data_url_crop: Optional[str] = None, timestamp: str = None) -> Dict[str, Any]:
    """
    Chama GPT-4 Vision para ler a placa.
    Envia imagem original + crop (se disponível) para melhor precisão.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    content: List[Dict[str, Any]] = [
        {"type": "text", "text": _build_prompt()},
        {
            "type": "image_url",
            "image_url": {"url": data_url, "detail": "high"},
        },
    ]

    # Se temos um crop da placa, manda junto pra ajudar
    if data_url_crop:
        content.append({
            "type": "text",
            "text": "Below is a ZOOMED crop of the license plate for precise reading. Focus on this crop:",
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url_crop, "detail": "high"},
        })

    # DEBUG: Salva informações da requisição
    if DEBUG_MODE and timestamp:
        debug_request = {
            "timestamp": timestamp,
            "model": "gpt-4o-mini",
            "has_crop": data_url_crop is not None,
            "image_size_full": len(data_url),
            "image_size_crop": len(data_url_crop) if data_url_crop else 0,
        }
        _debug_log(f"{timestamp}_request", debug_request)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=600,
        )

        raw_text = response.choices[0].message.content.strip() if response.choices[0].message.content else ""
        
        # DEBUG: Salva resposta RAW completa da API
        if DEBUG_MODE and timestamp:
            debug_response = {
                "timestamp": timestamp,
                "raw_text": raw_text,
                "raw_text_length": len(raw_text),
                "finish_reason": response.choices[0].finish_reason,
                "model_used": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                }
            }
            _debug_log(f"{timestamp}_response", debug_response)
            
            # Salva o raw_text puro em arquivo separado
            with open(os.path.join(DEBUG_DIR, f"{timestamp}_raw_response.txt"), "w", encoding="utf-8") as f:
                f.write(raw_text)

        # Tenta extrair JSON da resposta
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        return {
            "plate_number": None,
            "confidence": 0.0,
            "reasoning": f"Resposta inesperada: {raw_text}"
        }
    
    except Exception as e:
        # DEBUG: Salva erro
        if DEBUG_MODE and timestamp:
            debug_error = {
                "timestamp": timestamp,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            _debug_log(f"{timestamp}_error", debug_error)
        raise


# ======================================================
# VALIDAÇÃO DO RESULTADO (OTIMIZADA PARA PLACAS)
# ======================================================

def _validate_result(result: Dict[str, Any], sanity_issues: List[str]) -> Dict[str, Any]:
    """
    Valida e enriquece o resultado da API.
    """
    plate_number = result.get("plate_number") or ""
    confidence = float(result.get("confidence", 0.0))
    reasoning = result.get("reasoning", "")

    # Normaliza a placa
    plate_clean = _normalize_plate(plate_number)

    # Issues gerais (inclui blur/low_res etc)
    issues: List[str] = list(sanity_issues)

    # Lista separada só com o que realmente deve invalidar
    blocking_issues: List[str] = []

    # Debug: log do valor normalizado da placa
    if settings.DEBUG:
        print(f"[PLATE_AI] plate_number bruto: {plate_number} | normalizado: {plate_clean}")

    # ----------------------------
    # Falhas que realmente bloqueiam
    # ----------------------------
    if not plate_clean:
        blocking_issues.append("no_plate_detected")
        issues.append("no_plate_detected")

        return {
            "success": False,
            "plate_number": None,
            "confidence": 0.0,
            "issues": issues,
            "blocking_issues": blocking_issues,
            "raw_response": result,
        }

    # Valida formato da placa
    is_valid_format, format_type = _validate_plate_format(plate_clean)

    if not is_valid_format:
        msg = f"invalid_plate_format({plate_clean})"
        issues.append(msg)
        blocking_issues.append(msg)

    if confidence < MIN_CONFIDENCE:
        msg = f"low_confidence({confidence:.2f})"
        issues.append(msg)
        blocking_issues.append(msg)

    # ----------------------------
    # Validação de comprimento (só se formato for válido)
    # ----------------------------
    if is_valid_format and len(plate_clean) != 7:
        msg = f"invalid_plate_length({len(plate_clean)})"
        issues.append(msg)
        blocking_issues.append(msg)

    # ----------------------------
    # Resultado final
    # ----------------------------
    success = len(blocking_issues) == 0

    return {
        "success": success,
        "plate_number": plate_clean if success else None,
        "plate_format": format_type if success else "invalid",
        "confidence": confidence,
        "plate_color": result.get("plate_color", "unknown"),
        "plate_location": result.get("plate_location", "unknown"),
        "reasoning": reasoning,
        "issues": issues if issues else None,
        "blocking_issues": blocking_issues if blocking_issues else None,
        "raw_response": result,
    }


# ======================================================
# FUNÇÃO PRINCIPAL (ENTRY POINT)
# ======================================================

def read_plate(image_bytes: bytes) -> Dict[str, Any]:
    """
    Lê a placa do veículo de uma foto.

    Args:
        image_bytes: bytes da imagem (JPEG/PNG)

    Returns:
        Dict com: success, plate_number, confidence, issues, etc.
    """
    # Timestamp único para debug
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    pil_img = _img_bytes_to_pil(image_bytes)

    # DEBUG: Salva imagem original
    if DEBUG_MODE:
        _debug_save_image(pil_img, "01_original", timestamp)

    # 1) Checagens básicas (resolução, blur)
    sanity_issues = _basic_sanity_checks(pil_img)

    # 2) Pré-processamento da imagem completa
    processed = _preprocess_image(pil_img)
    
    # DEBUG: Salva imagem processada
    if DEBUG_MODE:
        _debug_save_image(processed, "02_processed", timestamp)
    
    data_url_full = _to_data_url_from_pil(processed)

    # 3) Tenta crop automático da placa
    crop = _auto_crop_plate(pil_img)
    data_url_crop = None
    if crop is not None:
        crop_processed = _preprocess_image(crop)
        
        # DEBUG: Salva crop processado
        if DEBUG_MODE:
            _debug_save_image(crop_processed, "03_crop", timestamp)
        
        data_url_crop = _to_data_url_from_pil(crop_processed)
    else:
        # DEBUG: Marca que não houve crop
        if DEBUG_MODE:
            with open(os.path.join(DEBUG_DIR, f"{timestamp}_03_crop_FAILED.txt"), "w") as f:
                f.write("Crop automático falhou - placa não detectada")

    # DEBUG: Salva informações iniciais
    if DEBUG_MODE:
        debug_info = {
            "timestamp": timestamp,
            "image_size": pil_img.size,
            "sanity_issues": sanity_issues,
            "crop_success": crop is not None,
        }
        _debug_log(f"{timestamp}_info", debug_info)

    # 4) Chama GPT-4 Vision (imagem completa + crop se disponível)
    try:
        api_result = _call_openai_vision(data_url_full, data_url_crop, timestamp)
    except Exception as e:
        return {
            "success": False,
            "plate_number": None,
            "confidence": 0.0,
            "issues": sanity_issues + [f"api_error({str(e)})"],
            "raw_response": None,
        }

    # 5) Valida resultado
    return _validate_result(api_result, sanity_issues)


# ======================================================
# FUNÇÃO COM RETRY (MELHORADA)
# ======================================================

def read_plate_with_retry(image_bytes: bytes) -> Dict[str, Any]:
    """
    Lê a placa SEM pré-processamento - a imagem original é sempre melhor.
    Removido sistema de retry com processamento que destruía a qualidade.
    """
    return read_plate(image_bytes)


# ======================================================
# FUNÇÃO COMPATÍVEL COM views_supabase_photos_process
# ======================================================

def validate_plate_with_ai(image_bytes: bytes) -> Dict[str, Any]:
    """
    Valida placa do veículo usando AI (GPT-4 Vision).
    
    Esta é a função compatível com views_supabase_photos_process.
    Internamente usa read_plate_with_retry para melhor precisão.
    
    Args:
        image_bytes: bytes da imagem (JPEG/PNG)
    
    Returns:
        Dict com: success, plate_number, confidence, issues, etc.
    """
    return read_plate_with_retry(image_bytes)
