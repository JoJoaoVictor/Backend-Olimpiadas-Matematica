"""
Gerador de PDF Otimizado com Playwright + MathJax SVG
RESOLVE: Sobrecarga de memória ao processar LaTeX e imagens no browser

FUNCIONALIDADES:
1. Renderiza LaTeX via MathJax (sem canvas)
2. Suporta imagens das questões (base64, URL, file_path)
3. Layout em 2 colunas com quebras inteligentes
4. Duas versões: SEM e COM resoluções
5. Cabeçalho/Rodapé institucional UNEMAT (customizável por prova)
"""
from app.core.config import settings
import io
import json
import base64
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from playwright.sync_api import sync_playwright
from app.utils.playwright_manager import PlaywrightManager

logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None


class AdvancedPDFGenerator:
    _BLANK_PAGE_TEXT_THRESHOLD = 50

    @staticmethod
    def _remove_blank_pages(pdf_bytes: bytes) -> bytes:
        """Remove páginas em branco do PDF gerado."""
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
        except Exception as e:
            logger.exception("Failed to remove blank pages")
            return pdf_bytes

    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        """Acessa campos de forma segura (dict ou objeto)."""
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    @staticmethod
    def _sanitize_latex(text: str) -> str:
        """Normaliza strings LaTeX do banco."""
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
            if idx != -1 and (idx == 0 or text[idx-1] != '\\'):
                text = text[:idx] + text[idx+1:]
        open_paren = len(re.findall(r'(?<!\\)\\\(', text))
        close_paren = len(re.findall(r'(?<!\\)\\\)', text))
        if open_paren != close_paren:
            text = re.sub(r'(?<!\\)\\\(', '', text)
            text = re.sub(r'(?<!\\)\\\)', '', text)
        text = re.sub(r'\$\s+', '$', text)
        text = re.sub(r'\s+\$', '$', text)
        return text

    @staticmethod
    def _load_static_img_base64(filename: str) -> str:
        """Carrega imagens estáticas (header/footer padrão) em base64."""
        try:
            base_path = Path(__file__).resolve().parent.parent.parent / "static" / "img" / filename
            if base_path.exists():
                with open(base_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{encoded}"
            return ""
        except Exception:
            return ""

    @staticmethod
    def _resolve_image(
        custom_value: Optional[str],
        default_filename: str
    ) -> str:
        if custom_value:
            if custom_value.startswith("data:"):
                return custom_value
            if custom_value.startswith("/"):
                base_url = getattr(settings, 'API_BASE_URL', 'http://localhost:8000').rstrip('/')
                return base_url + custom_value
            return custom_value
        return AdvancedPDFGenerator._load_static_img_base64(default_filename)

    @staticmethod
    def _get_image_source_for_question(q: Any) -> Optional[str]:
        base_url = getattr(settings, 'API_BASE_URL', 'http://localhost:8000')
        if base_url.endswith('/'):
            base_url = base_url[:-1]

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
                    if role == 'SMALL':
                        return 'question-img-small'
                    if role == 'LARGE':
                        return 'question-img-large'
            elif isinstance(images_field, dict):
                role = images_field.get('role', 'MEDIUM').upper()
                if role == 'SMALL':
                    return 'question-img-small'
                if role == 'LARGE':
                    return 'question-img-large'

        image_field = AdvancedPDFGenerator._get_field(q, "image")
        if isinstance(image_field, dict):
            role = image_field.get('role', 'MEDIUM').upper()
            if role == 'SMALL':
                return 'question-img-small'
            if role == 'LARGE':
                return 'question-img-large'

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

    @staticmethod
    def _build_exam_title(fase: str, anos: List[str], year: int = None) -> str:
        """
        Constrói o título da prova no padrão:
          OLIMPÍADA DE MATEMÁTICA DA UNEMAT – 2024 – 3ª FASE – ENSINO MÉDIO
          OLIMPÍADA DE MATEMÁTICA DA UNEMAT – 2024 – 3ª FASE – 4° e 5° Anos

        Fase:
          "1" → "1ª FASE"  |  "2" → "2ª FASE"  |  "3" → "3ª FASE"
          "Final" → "FINAL"  |  "1ª fase" → "1ª FASE"

        Anos (baseado nos labels do react-select):
          Contém "Médio"       → "ENSINO MÉDIO"
          Contém "Fundamental" → extrai número → "4° e 5° Anos"
          Só números (ex: "4º") → "4° Ano"
        """
        if year is None:
            year = datetime.now().year

        # ── Formata fase ──────────────────────────────────────────────────────
        fase_str = str(fase).strip() if fase else ""
        sufixos = {"1": "1ª", "2": "2ª", "3": "3ª"}

        if not fase_str or fase_str.lower() in ("none", ""):
            fase_texto = "1ª FASE"
        elif re.match(r"^\d+$", fase_str):
            # Número puro: "1" → "1ª FASE"
            fase_texto = f"{sufixos.get(fase_str, fase_str + 'ª')} FASE"
        elif re.match(r"^\d+[ªa°]?\s*fase$", fase_str, re.IGNORECASE):
            # "1ª fase", "2a fase" → normaliza
            num = re.search(r"\d+", fase_str).group()
            fase_texto = f"{sufixos.get(num, num + 'ª')} FASE"
        elif "final" in fase_str.lower():
            fase_texto = "3ª FASE"
        else:
            fase_texto = fase_str.upper()

        # ── Formata anos ──────────────────────────────────────────────────────
        # Normaliza para lista de strings
        if isinstance(anos, list):
            anos_lista = [str(a).strip() for a in anos if a and str(a).strip()]
        elif isinstance(anos, str) and anos.strip():
            anos_lista = [anos.strip()]
        else:
            anos_lista = []

        logger.info(f"_build_exam_title: fase_str={repr(fase_str)} fase_texto={repr(fase_texto)} anos_lista={repr(anos_lista)}")

        if not anos_lista:
            anos_texto = "Anos Diversos"
        else:
            # Detecta Ensino Médio:
            #   labels: "1º Médio", "2º Médio", "3º Médio"
            #   values: "1º", "2º", "3º" quando acompanhados de contexto médio
            # Regra: item com "Médio"/"Medio" OU value numérico puro <= 3 sem "Fundamental"
            tem_medio       = any("médio" in a.lower() or "medio" in a.lower() for a in anos_lista)
            tem_fundamental = any("fundamental" in a.lower() for a in anos_lista)

            # Se nenhum label explicita "Fundamental" ou "Médio",
            # usa os números para inferir: 1-3 = médio, 4-9 = fundamental
            if not tem_medio and not tem_fundamental:
                numeros_raw = []
                for a in anos_lista:
                    ns = re.findall(r"\d+", a)
                    if ns:
                        numeros_raw.append(int(ns[0]))
                if numeros_raw:
                    todos_medio      = all(n <= 3 for n in numeros_raw)
                    todos_fundamental = all(n >= 4 for n in numeros_raw)
                    if todos_medio:
                        tem_medio = True
                    elif todos_fundamental:
                        tem_fundamental = True

            if tem_medio and not tem_fundamental:
                anos_texto = "ENSINO MÉDIO"
            else:
                # Extrai apenas o primeiro número de cada item
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

    @staticmethod
    def _parse_alternatives(question: Any) -> Dict[str, str]:
        alt_raw = AdvancedPDFGenerator._get_field(question, "alternatives")
        if isinstance(alt_raw, dict):
            return {k: str(v).strip() if v else "" for k, v in alt_raw.items()}
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
                    return {k: str(v).strip() if v else "" for k, v in loaded.items()}
                if isinstance(loaded, str):
                    try:
                        parsed = json.loads(loaded)
                        return {k: str(v).strip() if v else "" for k, v in parsed.items()}
                    except:
                        pass
            except:
                pass
            lines = alt_raw.split('\n')
            alt_dict = {}
            for line in lines:
                match = re.match(r'^([a-e])\)\s*(.*)$', line.strip(), re.IGNORECASE)
                if match:
                    key = match.group(1).upper()
                    value = match.group(2).strip()
                    alt_dict[key] = value
            if alt_dict:
                return alt_dict
            pattern = r'["\']?([A-E])["\']?\s*:\s*["\']?([^,"\']+)["\']?'
            matches = re.findall(pattern, alt_raw, re.IGNORECASE)
            if matches:
                return {key.upper(): value.strip() for key, value in matches}
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

            alts_dict = AdvancedPDFGenerator._parse_alternatives(q)
            alts_html = ""
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
                        if include_resolution and key.upper() == correct_letter.upper():
                            alts_items.append(f'<span class="alt-item-red">{key}) {sanitized}</span>')
                        else:
                            alts_items.append(f'<span class="alt-item">{key}) {sanitized}</span>')
                alts_html = f'<div class="alternativas">{" ".join(alts_items)}</div>'

            resolution_html = ""
            if include_resolution:
                raw_res = ""
                for field in ["detailedResolution", "detailed_resolution", "resolution", "resolucao", "solucao", "answerExplanation", "explanation"]:
                    temp = AdvancedPDFGenerator._get_field(q, field, "")
                    if temp and temp.strip():
                        raw_res = temp
                        break
                if not raw_res:
                    raw_res = "Sem resolução disponível"
                resolution = AdvancedPDFGenerator._sanitize_latex(raw_res)
                resolution = resolution.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                resolution_html = f"""
                <div class="resolucao-box">
                    <p class="resolucao-label">Solução:</p>
                    <p class="resolucao-text">{resolution}</p>
                </div>
                """

            html_parts.append(f"""
            <div class="question-box">
                <p class="enunciado">{i}) {statement}</p>
                {img_html}
                {alts_html}
                {resolution_html}
            </div>
            """)
        return "\n".join(html_parts)

    @staticmethod
    def create_exam_pdf(
        exam: Any,
        questions: List[Any],
        options: Dict[str, Any] = None
    ) -> io.BytesIO:
        options = options or {}

        fase     = AdvancedPDFGenerator._get_field(exam, 'fase', '1ª FASE')
        anos_raw = AdvancedPDFGenerator._get_field(exam, 'anos', [])
        anos     = anos_raw if isinstance(anos_raw, list) else [str(anos_raw)]
        year     = AdvancedPDFGenerator._get_field(exam, 'ano', None)
        if not year:
            year = datetime.now().year
        titulo = AdvancedPDFGenerator._build_exam_title(fase, anos, year)

        custom_header = AdvancedPDFGenerator._get_field(exam, 'header_image', None)
        custom_footer = AdvancedPDFGenerator._get_field(exam, 'footer_image', None)

        header_img = AdvancedPDFGenerator._resolve_image(custom_header, "heder.PNG")
        footer_img = AdvancedPDFGenerator._resolve_image(custom_footer, "footer.PNG")

        raw_header_size = AdvancedPDFGenerator._get_field(exam, 'header_size', 100.0)
        raw_footer_size = AdvancedPDFGenerator._get_field(exam, 'footer_size', 100.0)
        header_size = max(50.0, min(150.0, float(raw_header_size or 100.0)))
        footer_size = max(50.0, min(150.0, float(raw_footer_size or 100.0)))

        header_width_mm = round(200 * header_size / 100, 1)
        footer_width_mm = round(160 * footer_size / 100, 1)

        questions_sem_resolucao = AdvancedPDFGenerator._render_questions_html(questions, False)
        questions_com_resolucao = AdvancedPDFGenerator._render_questions_html(questions, True)

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
                    svg: {{ fontCache: 'global' }},
                    startup: {{ typeset: false }}
                }};
            </script>
            <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-svg.js"></script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                @page {{ size: A4 portrait; margin: 5mm 10mm 5mm 10mm; }}
                body {{ font-family: 'Arial', Times, serif; font-size: 14pt; line-height: 1.4; color: #000; background: #fff; }}
                .print-table {{ width: 100%; border-collapse: collapse; }}
                .print-table thead {{ display: table-header-group; }}
                .print-table tfoot {{ display: table-footer-group; }}
                .print-table tr {{ page-break-inside: avoid; }}
                .header-space {{ width: 100%; text-align: center; margin-bottom: 2mm; }}
                .header-img {{ width: {header_width_mm}mm; height: auto; max-width: 100%; margin: 0 auto; }}
                .footer-space {{ position: fixed; bottom: 0; left: 0; width: 100%; text-align: center; z-index: 1000; margin: 0; }}
                .print-table tfoot td {{ height: 30mm; border: none; vertical-align: bottom; }}
                .footer-img {{ width: {footer_width_mm}mm; height: auto; max-width: 100%; margin: 0 auto; }}
                .content-wrapper {{ width: 100%; }}
                .titulo-prova {{ font-size: 14pt; font-weight: bold; margin: 0 0 1mm 33mm; text-align: left; }}
                .campos-aluno {{ font-size: 14pt; margin: 0 0 5mm 8mm; }}
                .campos-aluno p {{ margin-bottom: 1mm; }}
                .content {{ column-count: 2; column-gap: 20px; text-align: justify; margin: 0 4mm 15mm 4mm; }}
                .question-box {{ break-inside: avoid; page-break-inside: avoid; margin-bottom: 2mm; display: inline-block; width: 100%; min-height: 20px; }}
                .enunciado {{ font-family: 'Arial', Times, serif; font-size: 14pt; margin-bottom: 1px; text-align: justify; line-height: 1.3; word-wrap: break-word; overflow-wrap: break-word; min-height: 15px; }}
                .question-img {{ display: block; margin: 0.5mm auto; border: none; padding: 1mm; max-height: 70mm; width: auto; page-break-inside: avoid; }}
                .question-img-small {{ max-width: 50% !important; max-height: 280px !important; width: auto; height: auto; display: block; margin: 1px auto; }}
                .question-img-medium {{ max-width: 80% !important; max-height: 150px !important; width: auto; height: auto; display: block; margin: 1px auto; }}
                .question-img-large {{ max-width: 100% !important; height: auto; display: block; margin: 1px auto; }}
                .alternativas {{ font-family: 'Arial', Times, serif; font-size: 14pt; margin-top: 1.5mm; margin-bottom: 1.5mm; display: flex; flex-wrap: wrap; gap: 6mm; justify-content: space-between; }}
                .alt-item {{ white-space: nowrap; color: #000; flex-shrink: 0; }}
                .alt-item-red {{ white-space: nowrap; color: #cc0000; font-weight: bold; flex-shrink: 0; }}
                .resolucao-box {{ margin-top: 1mm; margin-bottom: 5mm; }}
                .resolucao-label {{ font-family: 'Arial', Times, serif; font-size: 14pt; margin-bottom: 1mm; color: #cc0000; font-weight: bold; }}
                .resolucao-text {{ color: #cc0000; font-size: 14pt; line-height: 1.3; }}
                .titulo-resolucoes {{ display: none; }}
                .page-break {{ page-break-after: always; display: block; height: 1px; }}
                .keep-together {{ page-break-inside: avoid !important; break-inside: avoid !important; }}
                .force-break {{ page-break-before: always !important; break-before: page !important; }}
            </style>
        </head>
        <body>
            <table class="print-table">
                <thead><tr><td><div class="header-space">{f'<img src="{header_img}" class="header-img" />' if header_img else ''}</div></td></tr></thead>
                <tfoot><tr><td><div class="footer-space">{f'<img src="{footer_img}" class="footer-img" />' if footer_img else ''}</div></td></tr></tfoot>
                <tbody><tr><td><div class="content-wrapper">
                    <div class="titulo-prova">{titulo}</div>
                    <div class="campos-aluno">
                        <p><strong>ALUNO(A):</strong>___________________________________________________________________________</p>
                        <p><strong>ESCOLA:</strong> _________________________________________ <strong>MUNICÍPIO:</strong> ________________________</p>
                    </div>
                    <div class="content">{questions_sem_resolucao}</div>
                    <div class="page-break"></div>
                    <div class="titulo-prova">{titulo}</div>
                    <div class="campos-aluno">
                        <p><strong>ALUNO(A):</strong>____________________________________________________________________________</p>
                        <p><strong>ESCOLA:</strong> _________________________________________ <strong>MUNICÍPIO:</strong> ________________________</p>
                    </div>
                    <div class="content">{questions_com_resolucao}</div>
                </div></td></tr></tbody>
            </table>
        </body>
        </html>
        """

        buffer = io.BytesIO()
        browser = PlaywrightManager.get_browser()
        page = None

        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_function(
                    "MathJax.typesetPromise ? MathJax.typesetPromise().then(() => true) : true",
                    timeout=15000
                )
            except Exception:
                logger.warning("MathJax não respondeu, continuando...")

            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
            )

            pdf_bytes = AdvancedPDFGenerator._remove_blank_pages(pdf_bytes)
            buffer.write(pdf_bytes)
            buffer.seek(0)
            logger.info(f"✅ PDF gerado com sucesso! Tamanho: {len(pdf_bytes)} bytes")
            return buffer

        except Exception as e:
            logger.error(f"❌ Erro na geração do PDF: {e}")
            raise
        finally:
            if page:
                page.close()

        @staticmethod
        def create_question_bank_pdf(questions: List[Any], options: Dict[str, Any] = None) -> io.BytesIO:
            fake_exam = {"fase": "Banco de Questões", "anos": ["Todos"], "ano": 2024}
            return AdvancedPDFGenerator.create_exam_pdf(fake_exam, questions, options)

        @staticmethod
        def create_statistical_report(data: Dict[str, Any], options: Dict[str, Any] = None) -> io.BytesIO:
            buffer = io.BytesIO()
            buffer.write(b"%PDF-1.4 (Report in development)")
            buffer.seek(0)
            return buffer