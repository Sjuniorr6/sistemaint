# import base64
# import io
# import json
# import re
# from typing import Any, Dict, List, Tuple

# from django.conf import settings

# from PIL import Image, ImageEnhance, ImageFilter
# import numpy as np

# # Import opcional do OpenCV
# try:
#     import cv2
# except Exception:
#     cv2 = None

# from openai import OpenAI

#     # ======================================================
#     #  CONFIGS DE VALIDAÇÃO
#     # ======================================================

# MIN_CONFIDENCE = 0.70  # ← Relaxado de 0.75 para 0.70
# MIN_WIDTH = 800  # ← Relaxado de 900
# MIN_HEIGHT = 600  # ← Relaxado de 700
# BLUR_THRESHOLD = 80.0  # ← Relaxado de 120.0 para aceitar mais imagens

# ODOMETER_MIN_DIGITS = 1  # ← Permite displays que mostram apenas alguns dígitos
# ODOMETER_MAX_DIGITS = 9


#     # ======================================================
#     #  FUNÇÕES AUXILIARES
#     # ======================================================

# def _img_bytes_to_pil(image_bytes: bytes) -> Image.Image:
#     """Converte bytes em PIL Image."""
#     return Image.open(io.BytesIO(image_bytes)).convert("RGB")


# def _estimate_blur_score(pil_img: Image.Image) -> float:
#     """Estima blur score usando Laplacian variance ou fallback."""
#     img = np.array(pil_img)

#     if img.shape[1] > 1600:
#             scale = 1600 / img.shape[1]
#             new_w = 1600
#             new_h = int(img.shape[0] * scale)
#             pil_resized = pil_img.resize((new_w, new_h))
#             img = np.array(pil_resized)

#         if cv2 is not None:
#             gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
#             lap = cv2.Laplacian(gray, cv2.CV_64F)
#             return float(lap.var())

#         gray = img.mean(axis=2)
#         gx = np.diff(gray, axis=1)
#         gy = np.diff(gray, axis=0)
#         score = float(np.var(gx) + np.var(gy))
#         return score


#     def _preprocess_image(pil_img: Image.Image) -> Image.Image:
#         """
#         Aplica pré-processamento para melhorar a qualidade da imagem:
#         - Sharpen (contra blur)
#         - Contrast enhancement
#         - Brightness ajustment se necessário
#         """
#         # Sharpen para compensar blur
#         img = pil_img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
#         # Aumentar contraste
#         enhancer = ImageEnhance.Contrast(img)
#         img = enhancer.enhance(1.3)
        
#         # Aumentar nitidez adicional
#         enhancer = ImageEnhance.Sharpness(img)
#         img = enhancer.enhance(1.5)
        
#         return img


#     def _to_data_url(image_bytes: bytes, apply_preprocessing: bool = True) -> str:
#         """
#         Converte bytes em data URL base64 (jpeg).
#         Opcionalmente aplica pré-processamento.
#         """
#         pil_img = _img_bytes_to_pil(image_bytes)
        
#         if apply_preprocessing:
#             pil_img = _preprocess_image(pil_img)

#         out = io.BytesIO()
#         pil_img.save(out, format="JPEG", quality=95, optimize=True)  # ← Quality aumentado
#         b64 = base64.b64encode(out.getvalue()).decode("utf-8")
#         return f"data:image/jpeg;base64,{b64}"


#     def _normalize_odometer_value(raw: str) -> str:
#         """Extrai apenas dígitos e retorna como string."""
#         if not raw:
#             return ""
#         digits = re.sub(r"\D+", "", raw)
#         return digits


#     def _basic_sanity_checks(pil_img: Image.Image) -> List[str]:
#         """
#         Checagens locais básicas.
#         Retorna lista de issues (strings).
#         """
#         issues = []

#         w, h = pil_img.size
#         if w < MIN_WIDTH or h < MIN_HEIGHT:
#             issues.append(f"image_low_resolution({w}x{h})")

#         blur_score = _estimate_blur_score(pil_img)
#         if blur_score < BLUR_THRESHOLD:
#             issues.append(f"image_blurry(blur_score={blur_score:.1f})")

#         return issues


#     # ======================================================
#     #  FUNÇÃO PRINCIPAL: IA + JSON SCHEMA
#     # ======================================================

#     def validate_odometer_with_ai(image_bytes: bytes) -> Tuple[bool, Dict[str, Any]]:
#         """
#         Valida foto do odômetro e extrai o valor.
#         Suporta odômetros analógicos, digitais (carro e moto).
        
#         Retorna:
#             (is_valid, result_dict)
#         """

#         # ---------- Checagens locais ----------
#         pil_img = _img_bytes_to_pil(image_bytes)
#         local_issues = _basic_sanity_checks(pil_img)
#         blur_score = _estimate_blur_score(pil_img)

#         # ---------- Chamada OpenAI ----------
#         client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", "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") or None)
#         model = getattr(settings, "OPENAI_ODOMETER_MODEL", "gpt-5.2")

#         # Aplica pré-processamento antes de enviar para IA
#         image_data_url = _to_data_url(image_bytes, apply_preprocessing=True)

#         schema = {
#             "type": "object",
#             "additionalProperties": False,
#             "properties": {
#                 "readable": {"type": "boolean"},
#                 "odometer_value_raw": {"type": "string"},
#                 "confidence": {"type": "number", "minimum": 0, "maximum": 1},
#                 "is_blurry": {"type": "boolean"},
#                 "is_cropped": {"type": "boolean"},
#                 "has_glare": {"type": "boolean"},
#                 "display_type": {
#                     "type": "string",
#                     "enum": ["analog", "digital_car", "digital_motorcycle", "unknown"]
#                 },
#                 "issues": {"type": "array", "items": {"type": "string"}},
#                 "notes": {"type": "string"},
#             },
#             "required": [
#                 "readable",
#                 "odometer_value_raw",
#                 "confidence",
#                 "is_blurry",
#                 "is_cropped",
#                 "has_glare",
#                 "display_type",
#                 "issues",
#                 "notes",
#             ],
#         }

#         instructions = (
#             "Você é um validador especializado de fotos de ODÔMETRO de veículos (carros e motos).\n"
#             "Objetivo: verificar se a foto permite ler o valor do odômetro (quilometragem total).\n\n"
            
#             "TIPOS DE DISPLAY:\n"
#             "- Analógico: números mecânicos rotativos (estilo antigo)\n"
#             "- Digital (carro): display LCD/LED geralmente no centro do painel\n"
#             "- Digital (moto): display compacto, odômetro pode estar em área pequena da tela\n\n"
            
#             "IMPORTANTE PARA DISPLAYS DIGITAIS:\n"
#             "- Em motos: o número GRANDE geralmente é velocímetro (pode ser 0). O odômetro fica "
#             "em áreas menores, pode ter indicação como 'ODO', 'TRIP', ou simplesmente números menores.\n"
#             "- Em carros: o odômetro geralmente está no display central, pode ter 'km' ou 'mi' próximo.\n"
#             "- NÃO confunda velocímetro com odômetro!\n"
#             "- Se a foto mostra o painel claramente, mesmo com algum blur, tente ler.\n\n"
            
#             "CRITÉRIOS DE ACEITAÇÃO (seja mais flexível):\n"
#             "- Aceite se conseguir ler os números com razoável certeza (não precisa estar perfeito)\n"
#             "- Aceite motion blur LEVE se os números ainda forem visíveis\n"
#             "- Aceite se algum dígito estiver parcialmente cortado mas a maioria está visível\n"
#             "- Rejeite apenas se realmente impossível ler (blur extremo, números totalmente ilegíveis)\n\n"
            
#             "O QUE FAZER:\n"
#             "1) Identifique o tipo de display (display_type)\n"
#             "2) Localize o odômetro (atenção: não é velocímetro!)\n"
#             "3) Tente ler o valor mesmo se houver algum blur\n"
#             "4) Se conseguir ler com confiança >= 60%, marque readable=true\n"
#             "5) Extraia todos os dígitos visíveis em odometer_value_raw\n"
#             "6) Dê confidence (0-1) realista baseado na sua certeza\n\n"
            
#             "ISSUES PADRONIZADAS:\n"
#             "- unreadable_numbers (apenas se REALMENTE ilegível)\n"
#             "- motion_blur (se houver, mas não impede necessariamente leitura)\n"
#             "- out_of_focus\n"
#             "- cropped_digits (se cortar informação importante)\n"
#             "- glare_reflection\n"
#             "- low_light\n"
#             "- wrong_display (se mostrar velocímetro ao invés de odômetro)\n"
#             "- angle_perspective\n\n"
            
#             "Se a foto está OK (mesmo que não perfeita), use readable=true e issues pode ser [].\n"
#             "Seja mais PERMISSIVO - o objetivo é extrair o valor se ele for visível."
#         )

#         try:
#             response = client.responses.create(
#                     model=model,
#                     reasoning={"effort": "high"},  # ou "xhigh" para pensar mais
#                     # temperature=0,  # (opcional) tende a dar extração mais estável/consistente
#                     instructions=instructions,
#                     input=[
#                         {
#                             "role": "user",
#                             "content": [
#                                 {"type": "input_text", "text": "Analise esta foto e extraia o valor do odômetro..."},
#                                 {"type": "input_image", "image_url": image_data_url},
#                             ],
#                         }
#                     ],
#                     text={
#                         "format": {
#                             "type": "json_schema",
#                             "name": "odometer_validation",
#                             "schema": schema,
#                         }
#                     },
#                 )


#             raw_json = response.output_text
#             ai_data = json.loads(raw_json)

#         except Exception as e:
#             result = {
#                 "type": "odometer_validation",
#                 "readable": False,
#                 "odometer_value": "",
#                 "confidence": 0.0,
#                 "readable_by_ai": False,
#                 "display_type": "unknown",
#                 "issues": list(set(local_issues + [f"ai_error({str(e)})"])),
#                 "blur_score": float(blur_score),
#             }
#             return False, result

#         # ---------- Pós-processamento ----------
#         odometer_value = _normalize_odometer_value(ai_data.get("odometer_value_raw", ""))

#         issues: List[str] = []
#         issues.extend(local_issues)
#         issues.extend(ai_data.get("issues", []) or [])

#         # Flags da IA
#         if ai_data.get("is_blurry"):
#             # Não adiciona automaticamente como issue crítico
#             pass
#         if ai_data.get("is_cropped"):
#             issues.append("cropped_digits")
#         if ai_data.get("has_glare"):
#             issues.append("glare_reflection")

#         # Sanity do número de dígitos (mais flexível)
#         if odometer_value:
#             if not (ODOMETER_MIN_DIGITS <= len(odometer_value) <= ODOMETER_MAX_DIGITS):
#                 issues.append(f"unexpected_digit_count({len(odometer_value)})")

#         confidence = float(ai_data.get("confidence", 0.0))
#         readable = bool(ai_data.get("readable", False))
#         display_type = ai_data.get("display_type", "unknown")

#         # Regra final de aceitação (mais flexível)
#         is_valid = (
#             readable
#             and confidence >= MIN_CONFIDENCE  # 0.70
#             and odometer_value != ""
#             and "unreadable_numbers" not in issues  # Apenas se REALMENTE ilegível
#             # Removido: cropped_digits não é mais automático reject
#         )

#         result = {
#             "type": "odometer_validation",
#             "readable": readable,
#             "odometer_value": odometer_value,
#             "confidence": confidence,
#             "readable_by_ai": readable,
#             "display_type": display_type,
#             "issues": sorted(list(set(issues))),
#             "blur_score": float(blur_score),
#             "notes": ai_data.get("notes", "") or "",
#         }

#         return is_valid, result