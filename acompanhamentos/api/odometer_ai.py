# api/odometer_ai.py
import base64
import io
import json
import re
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
BLUR_THRESHOLD = 40.0  # Reduzido de 80 para aceitar mais fotos legíveis

ODOMETER_MIN_DIGITS = 4
ODOMETER_MAX_DIGITS = 9

# Novo: validação de valores suspeitos
# "Suspeito" = possível trip meter, mas NÃO deve invalidar sozinho.
SUSPICIOUS_TRIP_MAX = 10000        # Trips raramente passam de 10k km
VERY_LOW_ODOMETER_WARN = 500       # Motos ou carros muito novos
VERY_LOW_ODOMETER_HARD_MIN = 10    # Abaixo disso é quase certamente erro (blocking)



# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================

def _img_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    """Converte bytes em PIL Image RGB."""
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


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
    """Pré-processamento leve: Sharpen, Contraste, Nitidez."""
    img = pil_img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Sharpness(img).enhance(1.4)
    return img


def _to_data_url_from_pil(pil_img: Image.Image) -> str:
    """Converte PIL em data URL base64 (jpeg)."""
    out = io.BytesIO()
    pil_img.save(out, format="JPEG", quality=95, optimize=True)
    b64 = base64.b64encode(out.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _normalize_digits(raw: str) -> str:
    """Extrai apenas dígitos."""
    if not raw:
        return ""
    return re.sub(r"\D+", "", raw)


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


# ======================================================
# CROP AUTOMÁTICO DO DISPLAY (MELHORADO)
# ======================================================

def _auto_crop_display(pil_img: Image.Image) -> Optional[Image.Image]:
    """
    Tenta localizar o maior "bloco" colorido do display digital
    (vermelho, laranja ou âmbar), e retorna um crop com margem.
    MELHORADO: ranges de cor mais amplos para pegar displays laranjas brasileiros.
    """
    arr = np.array(pil_img)

    if cv2 is not None:
        return _auto_crop_display_cv2(arr, pil_img)
    else:
        return _auto_crop_display_pil(arr, pil_img)


def _auto_crop_display_cv2(arr: np.ndarray, pil_img: Image.Image) -> Optional[Image.Image]:
    """Crop usando OpenCV (HSV nativo 0-180) - MELHORADO."""
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)

    # ---- Vermelho "baixo" (H 0~15) - AMPLIADO ----
    lower_red1 = np.array([0, 40, 60])  # S e V mais permissivos
    upper_red1 = np.array([15, 255, 255])

    # ---- Vermelho "alto" (H 165~180) - AMPLIADO ----
    lower_red2 = np.array([165, 40, 60])
    upper_red2 = np.array([180, 255, 255])

    # ---- Laranja / Âmbar (H 10~40) - AMPLIADO para displays brasileiros ----
    lower_orange = np.array([8, 40, 60])  # H mais baixo, S e V mais permissivos
    upper_orange = np.array([40, 255, 255])

    # ---- Amarelo (H 20~35) - para displays mais claros ----
    lower_yellow = np.array([20, 40, 80])
    upper_yellow = np.array([35, 255, 255])

    # ---- Azul (H 100~130) - NOVO: para displays azuis digitais brasileiros ----
    lower_blue = np.array([100, 50, 60])
    upper_blue = np.array([130, 255, 255])

    # ---- Magenta / Rosa (H 140~170) ----
    lower_magenta = np.array([140, 40, 60])
    upper_magenta = np.array([170, 255, 255])

    mask_r1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_r2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_o = cv2.inRange(hsv, lower_orange, upper_orange)
    mask_y = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_b = cv2.inRange(hsv, lower_blue, upper_blue)
    mask_m = cv2.inRange(hsv, lower_magenta, upper_magenta)

    mask = mask_r1 | mask_r2 | mask_o | mask_y | mask_b | mask_m

    # Limpa ruído - kernel maior para pegar displays maiores
    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=4)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Maior contorno por área
    c = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(c)

    # Regras mínimas reduzidas para pegar displays menores
    if w < 80 or h < 50:
        return None

    # Margem MAIOR para não cortar dígitos nas bordas
    pad_x = int(w * 0.20)
    pad_y = int(h * 0.20)
    x0 = max(x - pad_x, 0)
    y0 = max(y - pad_y, 0)
    x1 = min(x + w + pad_x, pil_img.size[0])
    y1 = min(y + h + pad_y, pil_img.size[1])

    cropped = pil_img.crop((x0, y0, x1, y1))

    # Regras mínimas reduzidas
    cw, ch = cropped.size
    if cw < 60 or ch < 30:
        return None

    return cropped


def _auto_crop_display_pil(arr: np.ndarray, pil_img: Image.Image) -> Optional[Image.Image]:
    """
    Fallback sem OpenCV — usa PIL HSV - MELHORADO.
    PIL HSV: H 0-255 (não 0-180 como OpenCV).
    """
    hsv_img = pil_img.convert("HSV")
    hsv_arr = np.array(hsv_img)

    H = hsv_arr[:, :, 0]   # 0..255
    S = hsv_arr[:, :, 1]   # 0..255
    V = hsv_arr[:, :, 2]   # 0..255

    # MELHORADO: ranges mais amplos
    # Vermelho em PIL HSV: H ~0-25 ou ~230-255
    mask_red = (
        ((H <= 25) | (H >= 230)) &
        (S >= 40) &
        (V >= 60)
    )
    
    # Laranja/Âmbar: H ~15-65 (AMPLIADO)
    mask_orange = (
        (H >= 15) & (H <= 65) &
        (S >= 40) &
        (V >= 60)
    )
    
    # Amarelo: H ~40-70
    mask_yellow = (
        (H >= 40) & (H <= 70) &
        (S >= 40) &
        (V >= 80)
    )
    
    # Azul: H ~115-150 (PIL usa 0-255, não 0-180)
    mask_blue = (
        (H >= 115) & (H <= 150) &
        (S >= 50) &
        (V >= 60)
    )
    
    # Magenta: H ~190-230
    mask_magenta = (
        (H >= 190) & (H <= 230) &
        (S >= 40) &
        (V >= 60)
    )

    mask = mask_red | mask_orange | mask_yellow | mask_blue | mask_magenta

    # Encontra bounding box dos pixels detectados
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any() or not cols.any():
        return None

    y0, y1 = np.where(rows)[0][[0, -1]]
    x0, x1 = np.where(cols)[0][[0, -1]]

    w = x1 - x0
    h = y1 - y0

    # Regras mínimas reduzidas
    if w < 80 or h < 50:
        return None

    # Margem maior
    pad_x = int(w * 0.20)
    pad_y = int(h * 0.20)
    x0 = max(x0 - pad_x, 0)
    y0 = max(y0 - pad_y, 0)
    x1 = min(x1 + pad_x, pil_img.size[0])
    y1 = min(y1 + pad_y, pil_img.size[1])

    cropped = pil_img.crop((x0, y0, x1, y1))

    cw, ch = cropped.size
    if cw < 60 or ch < 30:
        return None

    return cropped


# ======================================================
# CHAMADA À API OPENAI (PROMPT MELHORADO)
# ======================================================

def _build_prompt() -> str:
    """Prompt MELHORADO para leitura de odômetro veicular brasileiro."""
    return """You are analyzing a Brazilian vehicle dashboard photo to read the TOTAL odometer.

CRITICAL RULES:
1. The TOTAL odometer is almost always the LARGEST number displayed (typically 6-7 digits for used vehicles).
2. Trip meters ("parcial" in Portuguese) are usually SMALLER (3-5 digits) and often labeled.
3. In Brazilian vehicles, the total odometer is usually the most prominent number in the center of the display.
4. Display backgrounds can be RED, ORANGE, BLUE, WHITE, or any backlit color - focus on the NUMBERS, not the color.

STEP-BY-STEP PROCESS:
1. List ALL numeric values you can see in the display
2. Identify which is the TOTAL odometer based on:
   - It's typically the LARGEST/longest number (6-7 digits)
   - It's usually in the CENTER or most prominent position
   - It's NOT labeled as "trip", "parcial", "A", "B", or similar
3. Read ALL digits carefully, including leading zeros

COMMON PATTERNS:
- Total odometer: 219169 km (6 digits, center, large)
- Trip meter: 1904 (4 digits, smaller, labeled "parcial" or "trip")

Return ONLY valid JSON:
{
    "all_numbers_visible": ["<list all numbers you see>"],
    "odometer_raw": "<exact TOTAL odometer text>",
    "odometer_digits": "<only numeric digits of TOTAL odometer>",
    "trip_meter": "<trip value if visible, else null>",
    "unit": "km or miles",
    "confidence": <float 0.0 to 1.0>,
    "display_type": "digital or analog",
    "reasoning": "<explain why you chose this number as the total odometer>"
}

If you CANNOT read the odometer:
{"odometer_raw": null, "odometer_digits": null, "confidence": 0.0, "reasoning": "<why it failed>"}"""


def _call_openai_vision(data_url: str, data_url_crop: Optional[str] = None) -> Dict[str, Any]:
    """
    Chama GPT-4 Vision para ler o odômetro.
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

    # Se temos um crop do display, manda junto pra ajudar
    if data_url_crop:
        content.append({
            "type": "text",
            "text": "Below is a ZOOMED crop of the digital display for precise reading. Focus on this crop to identify the numbers:",
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": data_url_crop, "detail": "high"},
        })

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=600,
        temperature=0.0,
    )

    raw_text = response.choices[0].message.content.strip()

    # Tenta extrair JSON da resposta
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())

    return {
        "odometer_raw": None,
        "odometer_digits": None,
        "confidence": 0.0,
        "reasoning": f"Resposta inesperada: {raw_text}"
    }


# ======================================================
# VALIDAÇÃO DO RESULTADO (MELHORADA)
# ======================================================

def _validate_result(result: Dict[str, Any], sanity_issues: List[str]) -> Dict[str, Any]:
    """
    Valida e enriquece o resultado da API.
    Importante: agora existem issues BLOQUEANTES e issues de AVISO.
    """
    odometer_digits = result.get("odometer_digits") or ""
    confidence = float(result.get("confidence", 0.0))
    reasoning = result.get("reasoning", "")

    # Normaliza dígitos
    digits = _normalize_digits(odometer_digits)

    # Issues gerais (inclui blur/low_res etc)
    issues: List[str] = list(sanity_issues)

    # Lista separada só com o que realmente deve invalidar
    blocking_issues: List[str] = []

    # ----------------------------
    # Falhas que realmente bloqueiam
    # ----------------------------
    if not digits:
        blocking_issues.append("no_digits_detected")
        issues.append("no_digits_detected")

        return {
            "success": False,
            "odometer": None,
            "confidence": 0.0,
            "issues": issues,
            "blocking_issues": blocking_issues,
            "raw_response": result,
        }

    if len(digits) < ODOMETER_MIN_DIGITS:
        msg = f"too_few_digits({len(digits)})"
        issues.append(msg)
        blocking_issues.append(msg)

    if len(digits) > ODOMETER_MAX_DIGITS:
        msg = f"too_many_digits({len(digits)})"
        issues.append(msg)
        blocking_issues.append(msg)

    if confidence < MIN_CONFIDENCE:
        msg = f"low_confidence({confidence:.2f})"
        issues.append(msg)
        blocking_issues.append(msg)

    # ----------------------------
    # Conversão numérica
    # ----------------------------
    odometer_int = int(digits) if digits.isdigit() else None
    if odometer_int is None:
        issues.append("non_numeric_digits")
        blocking_issues.append("non_numeric_digits")

    # ----------------------------
    # Heurísticas de "trip meter" (AGORA SÓ WARNING)
    # ----------------------------
    # A regra certa não é "abaixo de 150k = inválido".
    # O que costuma indicar trip é: POUCOS DÍGITOS (<=5) + valor baixo.
    if odometer_int is not None:
        if odometer_int < SUSPICIOUS_TRIP_MAX:
            issues.append(f"suspicious_low_value({odometer_int})")

            # Se tem poucos dígitos, aí sim fica "provável trip", mas ainda WARNING (não bloqueia)
            if len(digits) <= 5:
                issues.append("likely_trip_meter_not_odometer")

        # Veículo pode ser novo -> warning apenas
        if odometer_int < VERY_LOW_ODOMETER_WARN:
            issues.append(f"very_low_odometer_warn({odometer_int})")

        # Isso aqui sim é quase sempre erro de leitura (blocking)
        if odometer_int < VERY_LOW_ODOMETER_HARD_MIN:
            msg = f"unreasonably_low_odometer({odometer_int})"
            issues.append(msg)
            blocking_issues.append(msg)

    # ----------------------------
    # Resultado final
    # ----------------------------
    success = len(blocking_issues) == 0

    return {
        "success": success,
        "odometer": odometer_int if success else odometer_int,  # mantém para debug mesmo se falhar
        "odometer_formatted": f"{odometer_int:,} km".replace(",", ".") if odometer_int else None,
        "confidence": confidence,
        "trip_meter": result.get("trip_meter"),
        "unit": result.get("unit", "km"),
        "display_type": result.get("display_type"),
        "reasoning": reasoning,
        "all_numbers_visible": result.get("all_numbers_visible", []),
        "issues": issues if issues else None,
        "blocking_issues": blocking_issues if blocking_issues else None,
        "raw_response": result,
    }



# ======================================================
# FUNÇÃO PRINCIPAL (ENTRY POINT)
# ======================================================

def read_odometer(image_bytes: bytes) -> Dict[str, Any]:
    """
    Lê o odômetro de uma foto do painel veicular.

    Args:
        image_bytes: bytes da imagem (JPEG/PNG)

    Returns:
        Dict com: success, odometer, confidence, issues, etc.
    """
    pil_img = _img_bytes_to_pil(image_bytes)

    # 1) Checagens básicas (resolução, blur)
    sanity_issues = _basic_sanity_checks(pil_img)

    # 2) Pré-processamento da imagem completa
    processed = _preprocess_image(pil_img)
    data_url_full = _to_data_url_from_pil(processed)

    # 3) Tenta crop automático do display digital
    crop = _auto_crop_display(pil_img)
    data_url_crop = None
    if crop is not None:
        crop_processed = _preprocess_image(crop)
        data_url_crop = _to_data_url_from_pil(crop_processed)

    # 4) Chama GPT-4 Vision (imagem completa + crop se disponível)
    try:
        api_result = _call_openai_vision(data_url_full, data_url_crop)
    except Exception as e:
        return {
            "success": False,
            "odometer": None,
            "confidence": 0.0,
            "issues": sanity_issues + [f"api_error({str(e)})"],
            "raw_response": None,
        }

    # 5) Valida resultado
    return _validate_result(api_result, sanity_issues)


# ======================================================
# FUNÇÃO COM RETRY (MELHORADA)
# ======================================================

def read_odometer_with_retry(image_bytes: bytes) -> Dict[str, Any]:
    """
    Tenta ler o odômetro com estratégia melhorada.
    Se detectar possível confusão com trip meter, tenta novamente com prompt reforçado.
    """
    result = read_odometer(image_bytes)

    # Se deu sucesso E não tem issues suspeitos, retorna
    issues = result.get("issues") or []
    is_likely_trip = any(i == "likely_trip_meter_not_odometer" for i in issues)

    # Se deu sucesso e não parece trip, retorna
    if result["success"] and not is_likely_trip:
        return result


    # Se detectou valor suspeito OU falhou, tenta segunda vez com processamento mais suave
    pil_img = _img_bytes_to_pil(image_bytes)

    # Aumenta brilho e contraste de forma mais conservadora
    enhanced = ImageEnhance.Brightness(pil_img).enhance(1.2)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.3)
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
    enhanced = enhanced.filter(ImageFilter.DETAIL)

    buf = io.BytesIO()
    enhanced.save(buf, format="JPEG", quality=98)
    enhanced_bytes = buf.getvalue()

    result2 = read_odometer(enhanced_bytes)

    # Retorna o resultado com MAIOR valor (assumindo que o maior é o odômetro real)
    odo1 = result.get("odometer") or 0
    odo2 = result2.get("odometer") or 0

    if odo2 > odo1:
        result2["retry"] = True
        result2["retry_reason"] = "Used enhanced image and picked larger value"
        return result2

    # Se ambos falharam ou o primeiro foi melhor
    return result


# ======================================================
# FUNÇÃO COMPATÍVEL COM views_supabase_photos_process
# ======================================================

def validate_odometer_with_ai(image_bytes: bytes) -> Dict[str, Any]:
    """
    Valida odômetro usando AI (GPT-4 Vision).
    
    Esta é a função compatível com views_supabase_photos_process.
    Internamente usa read_odometer_with_retry para melhor precisão.
    
    Args:
        image_bytes: bytes da imagem (JPEG/PNG)
    
    Returns:
        Dict com: success, odometer, confidence, issues, etc.
    """
    return read_odometer_with_retry(image_bytes)