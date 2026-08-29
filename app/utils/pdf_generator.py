"""
Gerador de PDF Otimizado com Playwright + MathJax SVG

Arquitetura de paginação:
  - Cabeçalho e rodapé são renderizados pelo mecanismo nativo do Chromium
    (display_header_footer), NÃO por <thead>/<tfoot> de tabela.
  - O corpo é um documento de blocos simples, permitindo que o multicol
    (column-count: 2) fragmente corretamente entre páginas.
  - Imagens de cabeçalho/rodapé são sempre embutidas como data URI base64,
    pois templates de header/footer do Chromium não carregam URLs externas.
"""
from app.core.config import settings
import io
import json
import base64
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.utils.playwright_manager import PlaywrightManager

logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None


class AdvancedPDFGenerator:
    _BLANK_PAGE_TEXT_THRESHOLD = 50

    # Alturas de fallback (mm) quando não é possível medir a imagem
    _FALLBACK_HEADER_H_MM = 25.0
    _FALLBACK_FOOTER_H_MM = 20.0

    # ────────────────────────────────────────────────────────────────
    # Utilitários genéricos
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _remove_blank_pages(pdf_bytes: bytes) -> bytes:
        """
        ATENÇÃO: não usar em provas com questões discursivas. Uma página com
        espaço de resolução tem pouquíssimo texto e seria removida por engano.
        Mantido apenas para compatibilidade.
        """
        if PdfReader is None or PdfWriter is None:
            return pdf_bytes
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            writer = PdfWriter()
            for page in reader.pages:
                text = page.extract_text() or ""
                clean_len = len(re.sub(r'\s+', '', text))
                if clean_len >= AdvancedPDFGenerator._BLANK_PAGE_TEXT_THRESHOLD:
                    writer.add_page(page)
            if len(writer.pages) == 0:
                return pdf_bytes
            writer.add_metadata({'/Title': 'Prova UNEMAT', '/Author': 'UNEMAT'})
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception:
            logger.exception("Failed to remove blank pages")
            return pdf_bytes

    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    @staticmethod
    def _sanitize_latex(text: str) -> str:
        if not text:
            return ""
        if text.startswith('\ufeff'):
            text = text[1:]
        text = re.sub(r'\\{3,}\(', r'\\(', text)
        text = re.sub(r'\\{3,}\)', r'\\)', text)
        text = re.sub(r'\\{3,}\[', r'\\[', text)
        text = re.sub(r'\\{3,}\]', r'\\]', text)
        replacements = [
            ('\\\\\\(', '\\('), ('\\\\\\)', '\\)'),
            ('\\\\\\[', '\\['), ('\\\\\\]', '\\]'),
            ('\\\\times', '\\times'), ('\\\\frac', '\\frac'),
            ('\\\\sqrt', '\\sqrt'), ('\\\\pi', '\\pi'),
            ('\\\\\\$', '\\$'),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        text = text.replace('\\\\', '\\')
        text = re.sub(r'R\$\s*(?=\d)', r'R\\$ ', text)
        text = re.sub(r'\$\s{0,3}\$', '', text)
        text = re.sub(r'\\\(\s{0,3}\\\)', '', text)
        dollar_count = text.count('$') - text.count('\\$')
        if dollar_count % 2 != 0:
            idx = text.rfind('$')
            if idx != -1 and (idx == 0 or text[idx - 1] != '\\'):
                text = text[:idx] + text[idx + 1:]
        open_paren = len(re.findall(r'(?<!\\)\\\(', text))
        close_paren = len(re.findall(r'(?<!\\)\\\)', text))
        if open_paren != close_paren:
            text = re.sub(r'(?<!\\)\\\(', '', text)
            text = re.sub(r'(?<!\\)\\\)', '', text)
        text = re.sub(r'\$\s+', '$', text)
        text = re.sub(r'\s+\$', '$', text)
        return text

    # ────────────────────────────────────────────────────────────────
    # Imagens de layout (cabeçalho / rodapé)
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _read_layout_image_bytes(custom_value: Optional[str], default_filename: str) -> Optional[bytes]:
        """Lê os bytes da imagem de layout, seja customizada ou o padrão estático."""
        if custom_value:
            # 1. Já é data URI
            if custom_value.startswith("data:"):
                try:
                    return base64.b64decode(custom_value.split(",", 1)[1])
                except Exception:
                    logger.warning("Data URI de layout inválida; usando padrão.")
                    custom_value = None
            # 2. Caminho relativo salvo pelo ExamService (/uploads/layouts/...)
            elif custom_value.startswith("/uploads/") or custom_value.startswith("uploads/"):
                rel = custom_value.removeprefix("/uploads/").removeprefix("uploads/")
                path = Path(settings.UPLOAD_PATH) / rel
                if path.exists():
                    return path.read_bytes()
                logger.warning(f"Imagem de layout não encontrada em disco: {path}")
                custom_value = None
            else:
                # URL externa não pode ser embutida no template do Chromium
                logger.warning(f"Imagem de layout em URL externa ignorada: {custom_value}")
                custom_value = None

        base_path = Path(__file__).resolve().parent.parent.parent / "static" / "img" / default_filename
        if base_path.exists():
            return base_path.read_bytes()
        logger.warning(f"Imagem padrão não encontrada: {base_path}")
        return None

    @staticmethod
    def _image_size_px(data: bytes) -> Tuple[int, int]:
        """Retorna (largura, altura) em pixels. (0, 0) se não for possível medir."""
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                return im.size
        except Exception:
            pass
        try:
            if data[:8] == b'\x89PNG\r\n\x1a\n':
                return (int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big'))
        except Exception:
            pass
        return (0, 0)

    @staticmethod
    def _to_data_uri(data: bytes) -> str:
        mime = "image/png"
        if data[:2] == b'\xff\xd8':
            mime = "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"

    @staticmethod
    def _prepare_layout_image(
        custom_value: Optional[str],
        default_filename: str,
        width_mm: float,
        fallback_height_mm: float,
    ) -> Tuple[str, float]:
        """Retorna (data_uri ou "", altura estimada em mm)."""
        data = AdvancedPDFGenerator._read_layout_image_bytes(custom_value, default_filename)
        if not data:
            return "", 0.0
        uri = AdvancedPDFGenerator._to_data_uri(data)
        w_px, h_px = AdvancedPDFGenerator._image_size_px(data)
        if w_px > 0 and h_px > 0:
            height_mm = width_mm * (h_px / w_px)
        else:
            height_mm = fallback_height_mm
        return uri, round(height_mm, 1)

    # ────────────────────────────────────────────────────────────────
    # Imagens das questões
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _get_image_source_for_question(q: Any) -> Optional[str]:
        base_url = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1').rstrip('/')

        src = None
        image_field = AdvancedPDFGenerator._get_field(q, "image")
        if image_field is not None:
            if hasattr(image_field, 'url') and image_field.url:
                src = image_field.url
            elif isinstance(image_field, dict) and 'url' in image_field:
                src = image_field['url']
            elif isinstance(image_field, str):
                src = image_field

        if src is None:
            images_field = AdvancedPDFGenerator._get_field(q, "images")
            if images_field:
                if isinstance(images_field, list) and len(images_field) > 0:
                    first = images_field[0]
                    if isinstance(first, dict) and 'src' in first:
                        src = first['src']
                    elif isinstance(first, str):
                        src = first
                elif isinstance(images_field, dict):
                    src = images_field.get('src')

        if src and isinstance(src, str) and src.startswith('/uploads/'):
            src = base_url + src

        return src

    @staticmethod
    def _get_image_class_for_question(q: Any) -> str:
        role = AdvancedPDFGenerator._get_field(q, "image_role")
        if role and isinstance(role, str):
            role = role.upper()
            if role == 'SMALL':
                return 'question-img-small'
            elif role == 'LARGE':
                return 'question-img-large'
            return 'question-img-medium'

        images_field = AdvancedPDFGenerator._get_field(q, "images")
        if images_field:
            if isinstance(images_field, list) and len(images_field) > 0:
                first = images_field[0]
                if isinstance(first, dict):
                    role = first.get('role', 'MEDIUM').upper()
                    if role == 'SMALL': return 'question-img-small'
                    if role == 'LARGE': return 'question-img-large'
            elif isinstance(images_field, dict):
                role = images_field.get('role', 'MEDIUM').upper()
                if role == 'SMALL': return 'question-img-small'
                if role == 'LARGE': return 'question-img-large'

        image_field = AdvancedPDFGenerator._get_field(q, "image")
        if isinstance(image_field, dict):
            role = image_field.get('role', 'MEDIUM').upper()
            if role == 'SMALL': return 'question-img-small'
            if role == 'LARGE': return 'question-img-large'

        return 'question-img-medium'

    @staticmethod
    def _get_image_style_attributes(q: Any) -> str:
        images_field = AdvancedPDFGenerator._get_field(q, "images")
        if images_field:
            if isinstance(images_field, list) and len(images_field) > 0:
                first = images_field[0]
                if isinstance(first, dict):
                    w = first.get('displayWidth')
                    h = first.get('displayHeight')
                    if w and h:
                        return f' style="max-width: {w}px; max-height: {h}px;"'
        return ""

    # ────────────────────────────────────────────────────────────────
    # Título
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_exam_title(fase: str, anos: List[str], year: int = None) -> str:
        if year is None:
            year = datetime.now().year

        fase_str = str(fase).strip() if fase else ""
        sufixos = {"1": "1ª", "2": "2ª", "3": "3ª"}

        if not fase_str or fase_str.lower() in ("none", ""):
            fase_texto = "1ª FASE"
        elif re.match(r"^\d+$", fase_str):
            fase_texto = f"{sufixos.get(fase_str, fase_str + 'ª')} FASE"
        elif re.match(r"^\d+[ªa°]?\s*fase$", fase_str, re.IGNORECASE):
            num = re.search(r"\d+", fase_str).group()
            fase_texto = f"{sufixos.get(num, num + 'ª')} FASE"
        elif "final" in fase_str.lower():
            fase_texto = "3ª FASE"
        else:
            fase_texto = fase_str.upper()

        if isinstance(anos, list):
            anos_lista = [str(a).strip() for a in anos if a and str(a).strip()]
        elif isinstance(anos, str) and anos.strip():
            anos_lista = [anos.strip()]
        else:
            anos_lista = []

        if not anos_lista:
            anos_texto = "Anos Diversos"
        else:
            tem_medio = any("médio" in a.lower() or "medio" in a.lower() for a in anos_lista)
            tem_fundamental = any("fundamental" in a.lower() for a in anos_lista)
            if not tem_medio and not tem_fundamental:
                numeros_raw = []
                for a in anos_lista:
                    ns = re.findall(r"\d+", a)
                    if ns:
                        numeros_raw.append(int(ns[0]))
                if numeros_raw:
                    todos_medio = all(n <= 3 for n in numeros_raw)
                    todos_fundamental = all(n >= 4 for n in numeros_raw)
                    if todos_medio:
                        tem_medio = True
                    elif todos_fundamental:
                        tem_fundamental = True
            if tem_medio and not tem_fundamental:
                anos_texto = "ENSINO MÉDIO"
            else:
                numeros = []
                for a in anos_lista:
                    ns = re.findall(r"\d+", a)
                    if ns:
                        numeros.append(ns[0])
                numeros_unicos = sorted(set(numeros), key=lambda x: int(x))
                if not numeros_unicos:
                    anos_texto = "Anos Diversos"
                elif len(numeros_unicos) == 1:
                    anos_texto = f"{numeros_unicos[0]}° Ano"
                elif len(numeros_unicos) == 2:
                    anos_texto = f"{numeros_unicos[0]}° e {numeros_unicos[1]}° Anos"
                else:
                    parte_inicial = ", ".join(f"{n}°" for n in numeros_unicos[:-1])
                    anos_texto = f"{parte_inicial} e {numeros_unicos[-1]}° Anos"

        return f"OLIMPÍADA DE MATEMÁTICA DA UNEMAT – {year} – {fase_texto} – {anos_texto}"

    # ────────────────────────────────────────────────────────────────
    # Alternativas
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_alternatives(question: Any) -> Dict[str, str]:
        alt_raw = AdvancedPDFGenerator._get_field(question, "alternatives")

        if isinstance(alt_raw, dict):
            return {k.lower(): str(v).strip() if v else "" for k, v in alt_raw.items()}

        if isinstance(alt_raw, str):
            if not alt_raw.strip():
                return {}
            try:
                clean = alt_raw.strip()
                if clean.startswith('"') and clean.endswith('"'):
                    clean = clean[1:-1]
                clean = clean.replace('\\"', '"')
                loaded = json.loads(clean)
                if isinstance(loaded, dict):
                    return {k.lower(): str(v).strip() if v else "" for k, v in loaded.items()}
                if isinstance(loaded, str):
                    try:
                        parsed = json.loads(loaded)
                        return {k.lower(): str(v).strip() if v else "" for k, v in parsed.items()}
                    except Exception:
                        pass
            except Exception:
                pass

            lines = alt_raw.split('\n')
            alt_dict = {}
            for line in lines:
                match = re.match(r'^([a-e])\)\s*(.*)$', line.strip(), re.IGNORECASE)
                if match:
                    alt_dict[match.group(1).lower()] = match.group(2).strip()
            if alt_dict:
                return alt_dict

            pattern = r'["\']?([A-E])["\']?\s*:\s*["\']?([^,"\']+)["\']?'
            matches = re.findall(pattern, alt_raw, re.IGNORECASE)
            if matches:
                return {key.lower(): value.strip() for key, value in matches}

        return {}

    @staticmethod
    def _extract_correct_letter(correct_alternative: str) -> str:
        if not correct_alternative:
            return ""
        text = correct_alternative.strip()
        if not text:
            return ""
        letter = text.upper()
        if letter in "ABCDE":
            return letter
        for char in text:
            if char.upper() in "ABCDE":
                return char.upper()
        return ""

    # ────────────────────────────────────────────────────────────────
    # Renderização das questões
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _render_questions_html(questions: List[Any], include_resolution: bool = False) -> str:
        html_parts = []
        for i, q in enumerate(questions, 1):
            raw_stmt = (
                AdvancedPDFGenerator._get_field(q, "question_statement") or
                AdvancedPDFGenerator._get_field(q, "questionStatement", "")
            )
            statement = AdvancedPDFGenerator._sanitize_latex(raw_stmt)
            statement = statement.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            q_img_src = AdvancedPDFGenerator._get_image_source_for_question(q)
            img_class = AdvancedPDFGenerator._get_image_class_for_question(q)
            style_attrs = AdvancedPDFGenerator._get_image_style_attributes(q)
            img_html = f'<img src="{q_img_src}" class="question-img {img_class}"{style_attrs} />' if q_img_src else ""

            hide_alts = bool(AdvancedPDFGenerator._get_field(q, "hide_alternatives", False))

            alts_html = ""
            if hide_alts:
                if not include_resolution:
                    alts_html = (
                        '<div class="resolucao-aluno-box">'
                        '<p class="resolucao-aluno-label">Resolução:</p>'
                        '<div class="resolucao-aluno-espaco"></div>'
                        '</div>'
                    )
            else:
                alts_dict = AdvancedPDFGenerator._parse_alternatives(q)
                if alts_dict:
                    alts_items = []
                    correct_letter = ""
                    if include_resolution:
                        correct_alt = (
                            AdvancedPDFGenerator._get_field(q, "correctAlternative") or
                            AdvancedPDFGenerator._get_field(q, "correct_alternative") or ""
                        )
                        correct_letter = AdvancedPDFGenerator._extract_correct_letter(correct_alt)
                    for key in sorted(alts_dict.keys()):
                        val = alts_dict[key]
                        if val:
                            sanitized = AdvancedPDFGenerator._sanitize_latex(str(val))
                            sanitized = sanitized.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            css = "alt-item-red" if (include_resolution and key.upper() == correct_letter.upper()) else "alt-item"
                            alts_items.append(f'<span class="{css}">{key.lower()}) {sanitized}</span>')
                    alts_html = f'<div class="alternativas">{" ".join(alts_items)}</div>'

            resolution_html = ""
            if include_resolution:
                raw_res = ""
                for field in ["detailedResolution", "detailed_resolution", "resolution",
                              "resolucao", "solucao", "answerExplanation", "explanation"]:
                    temp = AdvancedPDFGenerator._get_field(q, field, "")
                    if temp and str(temp).strip():
                        raw_res = temp
                        break
                if not raw_res:
                    raw_res = "Sem resolução disponível"
                resolution = AdvancedPDFGenerator._sanitize_latex(str(raw_res))
                resolution = resolution.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                resolution_html = (
                    '<div class="resolucao-box">'
                    '<p class="resolucao-label">Solução:</p>'
                    f'<p class="resolucao-text">{resolution}</p>'
                    '</div>'
                )

            html_parts.append(f"""
            <div class="question-box">
                <p class="enunciado">{i}) {statement}</p>
                {img_html}
                {alts_html}
                {resolution_html}
            </div>
            """)
        return "\n".join(html_parts)

    # ════════════════════════════════════════════════════════════════
    # Geração principal
    # ════════════════════════════════════════════════════════════════
    @staticmethod
    async def create_exam_pdf(
        exam: Any,
        questions: List[Any],
        options: Dict[str, Any] = None
    ) -> io.BytesIO:
        options = options or {}

        fase = AdvancedPDFGenerator._get_field(exam, 'fase', '1ª FASE')
        anos_raw = AdvancedPDFGenerator._get_field(exam, 'anos', [])
        anos = anos_raw if isinstance(anos_raw, list) else [str(anos_raw)]
        year = AdvancedPDFGenerator._get_field(exam, 'ano', None) or datetime.now().year
        titulo = AdvancedPDFGenerator._build_exam_title(fase, anos, year)

        raw_header_size = AdvancedPDFGenerator._get_field(exam, 'header_size', 100.0)
        raw_footer_size = AdvancedPDFGenerator._get_field(exam, 'footer_size', 100.0)
        header_size = max(50.0, min(150.0, float(raw_header_size or 100.0)))
        footer_size = max(50.0, min(150.0, float(raw_footer_size or 100.0)))

        # Largura máxima utilizável em A4 com margens laterais de 10mm
        header_width_mm = min(190.0, round(190 * header_size / 100, 1))
        footer_width_mm = min(190.0, round(160 * footer_size / 100, 1))

        header_uri, header_h_mm = AdvancedPDFGenerator._prepare_layout_image(
            AdvancedPDFGenerator._get_field(exam, 'header_image', None),
            "heder.PNG", header_width_mm, AdvancedPDFGenerator._FALLBACK_HEADER_H_MM
        )
        footer_uri, footer_h_mm = AdvancedPDFGenerator._prepare_layout_image(
            AdvancedPDFGenerator._get_field(exam, 'footer_image', None),
            "footer.PNG", footer_width_mm, AdvancedPDFGenerator._FALLBACK_FOOTER_H_MM
        )

        # Margens = altura da imagem + folga. Limitadas para não engolir a página.
        margin_top_mm = max(10.0, min(60.0, header_h_mm + 5.0)) if header_uri else 12.0
        margin_bottom_mm = max(10.0, min(60.0, footer_h_mm + 5.0)) if footer_uri else 12.0

        logger.info(
            f"Layout PDF: header={header_width_mm}x{header_h_mm}mm "
            f"footer={footer_width_mm}x{footer_h_mm}mm "
            f"margens(top/bottom)={margin_top_mm}/{margin_bottom_mm}mm"
        )

        questions_sem_resolucao = AdvancedPDFGenerator._render_questions_html(questions, False)
        questions_com_resolucao = AdvancedPDFGenerator._render_questions_html(questions, True)

        campos_aluno = (
            '<div class="campos-aluno">'
            '<p><strong>ALUNO(A):</strong>___________________________________________________________________________</p>'
            '<p><strong>ESCOLA:</strong> __________________________________________''<strong>MUNICÍPIO:</strong> _______________________</p>'
            '</div>'
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Prova UNEMAT</title>
            <script>
                window.MathJax = {{
                    loader: {{ load: ['output/svg'] }},
                    tex: {{
                        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                        displayMath: [['$$', '$$']]
                    }},
                    svg: {{ fontCache: 'local' }},
                    startup: {{ typeset: false }}
                }};
            </script>
            <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-svg.js"></script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                @page {{
                    size: A4 portrait;
                    margin: {margin_top_mm}mm 10mm {margin_bottom_mm}mm 10mm;
                }}

                body {{
                    font-family: 'Arial', Times, serif;
                    font-size: 14pt;
                    line-height: 1.4;
                    color: #000;
                    background: #fff;
                }}

                .secao {{ width: 100%; }}
                .secao-gabarito {{ break-before: page; page-break-before: always; }}

                .titulo-prova {{ font-size: 14pt; font-weight: bold; margin: 0 0 2mm 0; text-align: center; }}
                .campos-aluno {{ font-size: 14pt; margin: 0 0 5mm 0; }}
                .campos-aluno p {{ margin-bottom: 1mm; }}

                /* column-fill: auto faz as colunas preencherem a altura da página
                   sequencialmente, em vez de balancear. Essencial em mídia paginada. */
                .content {{
                    column-count: 2;
                    column-gap: 8mm;
                    column-fill: auto;
                    text-align: justify;
                }}

                /* display: block (NÃO inline-block). Caixas inline-block são
                   monolíticas no Chromium e quebram a fragmentação. */
                .question-box {{
                    display: block;
                    width: 100%;
                    break-inside: avoid;
                    page-break-inside: avoid;
                    margin-bottom: 3mm;
                }}

                .enunciado {{
                    font-family: 'Arial', Times, serif;
                    font-size: 14pt;
                    margin-bottom: 1mm;
                    text-align: justify;
                    line-height: 1.3;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                }}

                .question-img {{ display: block; margin: 1mm auto; border: none; max-height: 70mm; width: auto; }}
                .question-img-small  {{ max-width: 50% !important;  max-height: 60mm !important; width: auto; height: auto; }}
                .question-img-medium {{ max-width: 80% !important;  max-height: 45mm !important; width: auto; height: auto; }}
                .question-img-large  {{ max-width: 100% !important; max-height: 70mm !important; height: auto; }}

                .alternativas {{
                    font-family: 'Arial', Times, serif;
                    font-size: 14pt;
                    margin: 1.5mm 0;
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4mm;
                }}
                .alt-item     {{ white-space: nowrap; color: #000; flex-shrink: 0; }}
                .alt-item-red {{ white-space: nowrap; color: #cc0000; font-weight: bold; flex-shrink: 0; }}

                .resolucao-box   {{ margin: 1mm 0 5mm 0; }}
                .resolucao-label {{ font-size: 14pt; margin-bottom: 1mm; color: #cc0000; font-weight: bold; }}
                .resolucao-text  {{ color: #cc0000; font-size: 14pt; line-height: 1.3; }}

                /* Espaço de resolução do aluno: UMA caixa com altura declarada,
                   em vez de vários divs empilhados. Ajuste a altura aqui. */
                .resolucao-aluno-box    {{ margin: 2mm 0; width: 100%; }}
                .resolucao-aluno-label  {{ font-size: 13pt; font-weight: bold; color: #444; margin-bottom: 1mm; }}
                .resolucao-aluno-espaco {{ height: 28mm; width: 100%; }}

                /* No gabarito a resolução pode fluir livremente entre colunas */
                .content-gabarito .question-box {{
                    break-inside: auto !important;
                    page-break-inside: auto !important;
                }}
            </style>
        </head>
        <body>
            <section class="secao">
                <div class="titulo-prova">{titulo}</div>
                {campos_aluno}
                <div class="content">{questions_sem_resolucao}</div>
            </section>

            <section class="secao secao-gabarito">
                <div class="titulo-prova">{titulo}</div>
                {campos_aluno}
                <div class="content content-gabarito">{questions_com_resolucao}</div>
            </section>
        </body>
        </html>
        """

        header_template = (
            f'<div style="width:100%;margin:0;padding:0;text-align:center;font-size:1px;'
            f'-webkit-print-color-adjust:exact;">'
            f'<img src="{header_uri}" style="width:{header_width_mm}mm;height:auto;display:inline-block;"/>'
            f'</div>'
        ) if header_uri else '<div style="display:none"></div>'

        footer_template = (
            f'<div style="width:100%;margin:0;padding:0;text-align:center;font-size:1px;'
            f'-webkit-print-color-adjust:exact;">'
            f'<img src="{footer_uri}" style="width:{footer_width_mm}mm;height:auto;display:inline-block;"/>'
            f'</div>'
        ) if footer_uri else '<div style="display:none"></div>'

        # ─── Parâmetros de encaixe (ajuste aqui para calibrar o layout) ─────────
        ESPACO_MIN_MM   = 22     # escrita mínima por questão discursiva
        ESPACO_MAX_MM   = 55    # teto de escrita (evita uma questão inflar demais)
        IMG_MIN_MM      = 18     # piso da imagem ao encolher
        MARGEM_CAIXA_MM = 3      # deve bater com margin-bottom de .question-box
        SEGURANCA_MM    = 8      # folga por coluna contra erro de arredondamento

        altura_util_mm = 297.0 - margin_top_mm - margin_bottom_mm

        buffer = io.BytesIO()
        browser = await PlaywrightManager.get_browser()
        page = None

        try:
            # O viewport precisa ter a MESMA largura útil da página impressa
            # (A4 210mm − margens laterais de 10mm = 190mm), senão as colunas
            # medidas têm largura diferente das colunas do PDF e toda a
            # medição de altura sai errada.
            PX_POR_MM = 96 / 25.4
            largura_util_px = round((210.0 - 20.0) * PX_POR_MM)      # 718
            altura_util_px  = round(altura_util_mm * PX_POR_MM)

            page = await browser.new_page(
                viewport={"width": largura_util_px, "height": altura_util_px}
            )
            await page.emulate_media(media="print")
            await page.set_content(html_content, wait_until="domcontentloaded", timeout=60000)

            # 1. MathJax
            try:
                await page.wait_for_function(
                    "MathJax.typesetPromise ? MathJax.typesetPromise().then(() => true) : true",
                    timeout=15000
                )
            except Exception:
                logger.warning("MathJax não respondeu, continuando...")

            # 2. Aguarda TODAS as imagens carregarem.
            #    Medir antes disso produz alturas erradas e quebra o encaixe.
            try:
                await page.evaluate("""() => Promise.all(
                    [...document.images]
                        .filter(img => !img.complete)
                        .map(img => new Promise(r => { img.onload = img.onerror = r; }))
                )""")
            except Exception:
                logger.warning("Timeout aguardando imagens; medindo mesmo assim.")

            # 3. Encaixe modular: cada questão discursiva passa a ocupar um número
            #    inteiro de faixas da coluna, para que a coluna feche sem sobra.
            # 3. Empacotamento exato: agrupa questões por coluna e distribui a sobra
            try:
                relatorio = await page.evaluate("""
                    (p) => {
                        const PX_MM = 96 / 25.4;
                        const content = document.querySelector('.content:not(.content-gabarito)');
                        if (!content) return { erro: 'sem .content' };

                        const secao = content.closest('.secao');
                        const topo  = content.getBoundingClientRect().top
                                    - secao.getBoundingClientRect().top;

                        const alturaPag = p.alturaUtilMm * PX_MM;
                        const seg       = p.segurancaMm * PX_MM;
                        const margem    = p.margemCaixaMm * PX_MM;
                        const espacoMin = p.espacoMinMm * PX_MM;
                        const espacoMax = p.espacoMaxMm * PX_MM;
                        const imgMin    = p.imgMinMm * PX_MM;

                        // 1ª página tem menos espaço: título e campos do aluno ficam acima
                                                const col1 = alturaPag - topo - seg;
                        const colN = alturaPag - seg;

                        // Trava de segurança: se a capacidade calculada for absurda
                        // (zero, negativa, ou menor que o mínimo de escrita), é sinal
                        // de erro na medição de "topo" — não deixa degradar em silêncio.
                        if (col1 < espacoMin || colN < espacoMin) {
                            return {
                                erro: 'capacidade de coluna inválida',
                                topo_mm: Math.round(topo / PX_MM),
                                alturaPag_mm: Math.round(alturaPag / PX_MM),
                                col1_mm: Math.round(col1 / PX_MM),
                                colN_mm: Math.round(colN / PX_MM)
                            };
                        }
                        const capacidade = (i) => (i < 2 ? col1 : colN);
                        
                        // ── 1. Mede o conteúdo de cada caixa, sem espaço de escrita ──
                        const itens = [...content.querySelectorAll('.question-box')].map((box, i) => {
                            const espaco = box.querySelector('.resolucao-aluno-espaco');
                            if (espaco) espaco.style.height = '0px';
                            const img = box.querySelector('.question-img');
                            if (img) img.style.maxHeight = '';
                            return {
                                n: i + 1, box, espaco, img,
                                base: box.getBoundingClientRect().height,
                                imgMm: null
                            };
                        });

                        // ── 2. Encolhe a imagem só de quem não cabe nem sozinho ──
                        const capMin = Math.min(col1, colN);
                        itens.forEach(it => {
                            const precisa = it.base + (it.espaco ? espacoMin : 0) + margem;
                            if (precisa > capMin && it.img) {
                                const hImg = it.img.getBoundingClientRect().height;
                                const nova = Math.max(imgMin, hImg - (precisa - capMin));
                                it.img.style.maxHeight = nova + 'px';
                                it.imgMm = Math.round(nova / PX_MM);
                                it.base = it.box.getBoundingClientRect().height;
                            }
                        });

                        // ── 3. Empacota: enche cada coluna até o limite ──
                        const colunas = [];
                        let atual = { itens: [], usado: 0, cap: capacidade(0) };
                        itens.forEach(it => {
                            const precisa = it.base + (it.espaco ? espacoMin : 0) + margem;
                            if (atual.itens.length > 0 && atual.usado + precisa > atual.cap) {
                                colunas.push(atual);
                                atual = { itens: [], usado: 0, cap: capacidade(colunas.length) };
                            }
                            atual.itens.push(it);
                            atual.usado += precisa;
                        });
                        if (atual.itens.length) colunas.push(atual);

                        // ── 4. Distribui a sobra entre as discursivas de cada coluna ──
                        const relat = [];
                        colunas.forEach((col, ci) => {
                            const disc  = col.itens.filter(it => it.espaco);
                            const sobra = Math.max(0, (col.cap - col.usado) * 0.95);
                            const extra = disc.length ? sobra / disc.length : 0;

                            disc.forEach(it => {
                                const h = Math.min(espacoMax, espacoMin + extra);
                                it.espaco.style.height = h + 'px';
                                it.escritaMm = Math.round(h / PX_MM);
                            });

                            relat.push({
                                col: ci + 1,
                                cap_mm: Math.round(col.cap / PX_MM),
                                questoes: col.itens.map(it => ({
                                    q: it.n,
                                    tipo: it.espaco ? 'disc' : 'alt',
                                    conteudo_mm: Math.round(it.base / PX_MM),
                                    escrita_mm: it.escritaMm ?? null,
                                    img_mm: it.imgMm
                                }))
                            });
                        });

                        return {
                            coluna_pag1_mm: Math.round(col1 / PX_MM),
                            coluna_demais_mm: Math.round(colN / PX_MM),
                            colunas: relat
                        };
                    }
                """, {
                    "alturaUtilMm":  altura_util_mm,
                    "espacoMinMm":   ESPACO_MIN_MM,
                    "espacoMaxMm":   ESPACO_MAX_MM,
                    "imgMinMm":      IMG_MIN_MM,
                    "margemCaixaMm": MARGEM_CAIXA_MM,
                    "segurancaMm":   SEGURANCA_MM,
                })
                logger.info(f" COLUNAS: {relatorio}")
            except Exception as e:
                logger.warning(f"Empacotamento falhou, usando alturas do CSS: {e}")

            # 4. Geração
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=header_template,
                footer_template=footer_template,
                margin={
                    "top":    f"{margin_top_mm}mm",
                    "bottom": f"{margin_bottom_mm}mm",
                    "left":   "10mm",
                    "right":  "10mm",
                },
            )

            buffer.write(pdf_bytes)
            buffer.seek(0)
            logger.info(f"✅ PDF gerado com sucesso! Tamanho: {len(pdf_bytes)} bytes")
            return buffer

        except Exception as e:
            logger.error(f"❌ Erro na geração do PDF: {e}")
            raise
        finally:
            if page:
                await page.close()

    # ────────────────────────────────────────────────────────────────
    @staticmethod
    async def create_question_bank_pdf(questions: List[Any], options: Dict[str, Any] = None) -> io.BytesIO:
        fake_exam = {"fase": "Banco de Questões", "anos": ["Todos"], "ano": datetime.now().year}
        return await AdvancedPDFGenerator.create_exam_pdf(fake_exam, questions, options)

    @staticmethod
    async def create_statistical_report(data: Dict[str, Any], options: Dict[str, Any] = None) -> io.BytesIO:
        buffer = io.BytesIO()
        buffer.write(b"%PDF-1.4 (Report in development)")
        buffer.seek(0)
        return buffer