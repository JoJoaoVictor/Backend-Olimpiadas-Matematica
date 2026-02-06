# app/utils/pdf_generator.py

"""
Gerador de PDF Otimizado com Playwright + MathJax SVG
RESOLVE: Sobrecarga de memória ao processar LaTeX e imagens no browser

FUNCIONALIDADES:
1. Renderiza LaTeX via MathJax (sem canvas)
2. Suporta imagens das questões (base64, URL, file_path)
3. Layout em 2 colunas com quebras inteligentes
4. Duas versões: SEM e COM resoluções
5. Cabeçalho/Rodapé institucional UNEMAT
"""

import io
import json
import base64
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    PdfReader = PdfWriter = None


class AdvancedPDFGenerator:

    # Mínimo de caracteres para considerar página com conteúdo (páginas só header/footer = 0)
    _BLANK_PAGE_TEXT_THRESHOLD = 50

    @staticmethod
    def _remove_blank_pages(pdf_bytes: bytes) -> bytes:
        """
        Remove páginas em branco (apenas header/footer) do PDF gerado.
        Páginas com menos de _BLANK_PAGE_TEXT_THRESHOLD caracteres são consideradas vazias.
        Não altera CSS/HTML - correção pós-geração.
        """
        if PdfReader is None or PdfWriter is None:
            return pdf_bytes
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            writer = PdfWriter()
            for page in reader.pages:
                text = page.extract_text() or ""
                # Remove espaços; páginas só com header/footer têm pouco ou nenhum texto
                clean_len = len(re.sub(r'\s+', '', text))
                if clean_len >= AdvancedPDFGenerator._BLANK_PAGE_TEXT_THRESHOLD:
                    writer.add_page(page)
            if len(writer.pages) == 0:
                return pdf_bytes  # Fallback: mantém original se todas fossem "vazias"
            writer.add_metadata({
                '/Title': 'Prova UNEMAT',
                '/Author': 'UNEMAT'
            })
            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception as e:
            logger.exception("Failed to remove blank pages from PDF")
            return pdf_bytes
    
    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        """Acessa campos de forma segura (dict ou objeto)"""
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    # ============================================================================
# PATCH CORRETO - Substituir APENAS linhas 78-112 do pdf_generator.py
# ============================================================================
# 
# ATENÇÃO: NÃO delete a função _get_field (linha 72-76)!
# Substitua APENAS a função _sanitize_latex (linha 78-112)
#
# ============================================================================

    @staticmethod
    def _sanitize_latex(text: str) -> str:
        """
        Normaliza strings LaTeX do banco - corrige TODOS os casos problemáticos.
        OTIMIZADO: Detecta duplo escape automaticamente (questão 9197).
        Ordem CRÍTICA: mais específico primeiro (questões b042, f855, etc).
        
        FIX 2025-02-05: Proteção contra LaTeX quebrado que causa layout cascata
        """
        if not text:
            return ""
        
        # Remove BOM do UTF-8 se presente
        if text.startswith('\ufeff'):
            text = text[1:]
        
        # OTIMIZAÇÃO: Detectar e corrigir LaTeX duplo/triplo escape
        # Problema: "\\\\(\\pi r^2\\)" → deve ser "\\(\\pi r^2\\)"
        # Busca padrão: 3+ barras antes de parêntese/colchete
        text = re.sub(r'\\{3,}\(', r'\\(', text)
        text = re.sub(r'\\{3,}\)', r'\\)', text)
        text = re.sub(r'\\{3,}\[', r'\\[', text)
        text = re.sub(r'\\{3,}\]', r'\\]', text)
        
        # Ordem CRÍTICA: mais específico primeiro
        replacements = [
            ('\\\\\\(', '\\('), ('\\\\\\)', '\\)'),
            ('\\\\\\[', '\\['), ('\\\\\\]', '\\]'),
            ('\\\\times', '\\times'), ('\\\\frac', '\\frac'),
            ('\\\\sqrt', '\\sqrt'), ('\\\\pi', '\\pi'),
            ('\\\\\\$', '\\$'),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        
        # Final: escapes duplos para simples
        text = text.replace('\\\\', '\\')
        
        # ========== PROTEÇÃO CONTRA LATEX QUEBRADO (FIX LAYOUT CASCATA) ==========
        
        # 1. PROTEGER R$ (valores monetários) - Principal causa do problema
        # "R$ 13,00" → MathJax vê "$13,00$" → SVG quebrado → layout cascata
        text = re.sub(r'R\$\s*(?=\d)', r'R\\$ ', text)
        
        # 2. REMOVER FÓRMULAS VAZIAS (geram SVG com altura=0 → quebra column-count)
        text = re.sub(r'\$\s{0,3}\$', '', text)           # Remove $ $, $  $, $   $
        text = re.sub(r'\\\(\s{0,3}\\\)', '', text)       # Remove \( \), \(  \), etc.
        
        # 3. BALANCEAR DELIMITADORES $ (remove $ ímpar que quebra parser)
        dollar_count = text.count('$') - text.count('\\$')  # Ignora \$ escapado
        if dollar_count % 2 != 0:
            idx = text.rfind('$')
            if idx != -1 and (idx == 0 or text[idx-1] != '\\'):
                text = text[:idx] + text[idx+1:]
        
        # 4. REMOVER DELIMITADORES \( \) ÓRFÃOS (desbalanceados)
        open_paren = len(re.findall(r'(?<!\\)\\\(', text))
        close_paren = len(re.findall(r'(?<!\\)\\\)', text))
        if open_paren != close_paren:
            text = re.sub(r'(?<!\\)\\\(', '', text)
            text = re.sub(r'(?<!\\)\\\)', '', text)
        
        # 5. LIMPAR ESPAÇOS EM FÓRMULAS (causa altura errada no MathJax)
        text = re.sub(r'\$\s+', '$', text)      # Remove espaço após $
        text = re.sub(r'\s+\$', '$', text)      # Remove espaço antes de $
        
        return text

    @staticmethod
    def _load_static_img_base64(filename: str) -> str:
        """
        Carrega imagens estáticas (header/footer) em base64
        Procura em: app/static/img/
        """
        try:
            # Caminho: app/utils/pdf_generator.py -> app/ -> static/img/
            base_path = Path(__file__).resolve().parent.parent.parent / "static" / "img" / filename
            
            if base_path.exists():
                with open(base_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{encoded}"
            else:
                print(f"⚠️ Imagem não encontrada: {base_path}")
            return ""
        except Exception as e:
            print(f"⚠️ Erro ao carregar {filename}: {e}")
            return ""

    @staticmethod
    def _process_question_image(image_data: Any) -> Optional[str]:
        """
        Processa imagem da questão em múltiplos formatos
        
        Aceita:
        - Base64: "data:image/png;base64,iVBORw0KG..."
        - URL: "https://exemplo.com/imagem.png"
        - File Path: "/uploads/questao_123.png"
        - Dict: {"file_path": "...", "filePath": "..."}
        """
        if not image_data:
            return None
        
        # Caso 1: Já é base64 ou URL
        if isinstance(image_data, str):
            if image_data.startswith('data:image'):
                return image_data  # Base64
            elif image_data.startswith('http'):
                return image_data  # URL externa
            elif image_data.startswith('/') or image_data.startswith('uploads/'):
                # File path relativo - tenta carregar
                try:
                    file_path = Path(image_data)
                    if not file_path.is_absolute():
                        # Assume que está em static/uploads
                        file_path = Path(__file__).resolve().parent.parent / "static" / image_data.lstrip('/')
                    
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            encoded = base64.b64encode(f.read()).decode('utf-8')
                            ext = file_path.suffix.lower().replace('.', '')
                            mime = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'gif'] else "image/png"
                            return f"data:{mime};base64,{encoded}"
                except Exception as e:
                    print(f"⚠️ Erro ao carregar imagem {image_data}: {e}")
                    return None
        
        # Caso 2: É um dict com file_path
        elif isinstance(image_data, dict):
            file_path = image_data.get('file_path') or image_data.get('filePath')
            if file_path:
                return AdvancedPDFGenerator._process_question_image(file_path)
        
        return None

    @staticmethod
    def _build_exam_title(fase: str, anos: List[str], year: int = None) -> str:
        """
        Constrói título idêntico ao frontend
        """
        if year is None:
            year = datetime.now().year
            
        fase_texto = fase.upper() if fase else "1ª FASE"
        anos_texto = "Anos Diversos"
        
        if anos:
            # CORREÇÃO: Frontend agora envia "Xº Fundamental" ou "Xº Médio"
            import re
            anos_numeros = []
            tem_medio = False
            tem_fundamental = False
            
            if isinstance(anos, list):
                # Processa cada item da lista
                for item in anos:
                    if item:
                        item_str = str(item)                     
                        # Verifica se é Ensino Médio ou Fundamental
                        if 'médio' in item_str.lower() or 'medio' in item_str.lower():
                            tem_medio = True
                        elif 'fundamental' in item_str.lower():
                            tem_fundamental = True
                        # Extrai o número
                        numeros = re.findall(r'\d+', item_str)
                        anos_numeros.extend(numeros)
            
            elif isinstance(anos, str):
                if 'médio' in anos.lower() or 'medio' in anos.lower():
                    tem_medio = True
                elif 'fundamental' in anos.lower():
                    tem_fundamental = True
                anos_numeros = re.findall(r'\d+', anos)
            
            if anos_numeros:
                # Remove duplicados e ordena numericamente
                anos_unicos = sorted(set(anos_numeros), key=lambda x: int(x))    
                # NOVO: Detecta pelo texto "Médio" no lugar dos números
                if tem_medio and not tem_fundamental:
                    # Se tem algum "Médio" e NÃO tem "Fundamental" → ENSINO MÉDIO
                    anos_texto = "ENSINO MÉDIO"
                else:
                    # Para Fundamental (ou mistura) → formata os anos específicos
                    labels = [f"{val}º" for val in anos_unicos]
                    
                    if len(labels) > 1:
                        if len(labels) > 2:
                            parte_inicial = ', '.join(labels[:-1])
                            anos_texto = f"{parte_inicial} e {labels[-1]} Anos"
                        else:
                            # 2 anos: "4º e 5º Anos"
                            anos_texto = f"{labels[0]} e {labels[1]} Anos"
                    else:
                        # 1 ano: "4º Ano"
                        anos_texto = f"{labels[0]} Ano"
        
        return f"OLIMPÍADA DE MATEMÁTICA DA UNEMAT – {year} – {fase_texto} – {anos_texto}"
    
    @staticmethod
    def _parse_alternatives(question: Any) -> Dict[str, str]:
        """
        Extrai alternativas e retorna dict limpo.
        OTIMIZADO: Remove espaços extras automaticamente (problema de 5+ questões).
        Retorna: {"A": "texto", "B": "texto", ...}
        """
        alternatives_raw = AdvancedPDFGenerator._get_field(question, "alternatives")
        
        if isinstance(alternatives_raw, dict):
            # OTIMIZAÇÃO: Remove espaços extras em valores dict
            return {k: str(v).strip() if v else "" for k, v in alternatives_raw.items()}
        
        if isinstance(alternatives_raw, str):
            # Se vazio, retorna dict vazio (problema: 4 questões com alternatives="")
            if not alternatives_raw or not alternatives_raw.strip():
                return {}
            
            try:
                # Remove aspas extras e espaços em branco
                clean = alternatives_raw.strip()
                
                # Se começa e termina com aspas, remove
                if clean.startswith('"') and clean.endswith('"'):
                    clean = clean[1:-1]
                
                # Remove barras de escape
                clean = clean.replace('\\"', '"')
                
                # Tenta fazer parse do JSON
                loaded = json.loads(clean)
                if isinstance(loaded, dict):
                    # OTIMIZAÇÃO: Remove espaços extras após parse
                    return {k: str(v).strip() if v else "" for k, v in loaded.items()}
                elif isinstance(loaded, str):
                    # Se for string, tenta parse novamente
                    try:
                        parsed = json.loads(loaded)
                        return {k: str(v).strip() if v else "" for k, v in parsed.items()}
                    except:
                        pass
            except Exception as e:
                print(f"⚠️ Erro ao parsear alternativas: {e}")
                print(f"⚠️ Raw alternatives: {alternatives_raw}")
        
        # Fallback: procura por padrão A: ..., B: ...
        if isinstance(alternatives_raw, str):
            pattern = r'["\']?([A-E])["\']?\s*:\s*["\']?([^,"\']+)["\']?'
            matches = re.findall(pattern, alternatives_raw, re.IGNORECASE)
            if matches:
                # OTIMIZAÇÃO: Remove espaços extras no fallback também
                return {key.upper(): value.strip() for key, value in matches}
        
        return {}

    @staticmethod
    def _extract_correct_letter(correct_alternative: str) -> str:
        """
        Extrai letra da alternativa correta (OTIMIZADO COM FALLBACK ROBUSTO).
        
        Dados já migrados para formato normalizado: "A", "B", "C", "D", "E"
        Mas mantém fallback para dados antigos e inválidos (3 questões: 42a7, a3d7, f855).
        
        Performance:
        - String comparison (super rápido) em vez de 3 regex
        - ~95% dos casos: 1 strip + 1 comparação
        - Fallback ROBUSTO: encontra PRIMEIRA letra A-E em qualquer lugar da string
        """
        if not correct_alternative:
            return ""
        
        text = correct_alternative.strip()
        if not text:
            return ""
        
        letter = text.upper()
        
        # Caso comum (99%): dados já normalizados - apenas uma letra
        if letter in "ABCDE":
            return letter
        
        # FALLBACK ROBUSTO: Para questões com dados inválidos
        # Exemplos: "DE quem mais usa somente celular" → extrai "D"
        #           "44 anos" → procura primeira letra A-E
        #           "R$ 160,00" → procura primeira letra A-E
        for char in text:
            if char.upper() in "ABCDE":
                return char.upper()
        
        # Se nada encontrado, retorna vazio
        return ""

    @staticmethod
    def _render_questions_html(questions: List[Any], include_resolution: bool = False) -> str:
        """
        Renderiza HTML das questões
        CORREÇÃO: Escapa caracteres problemáticos para HTML
        """
        html_parts = []
        
        for i, q in enumerate(questions, 1):
            
            # Enunciado (sempre preto)
            raw_stmt = (
                AdvancedPDFGenerator._get_field(q, "question_statement") or
                AdvancedPDFGenerator._get_field(q, "questionStatement", "")
            )
            statement = AdvancedPDFGenerator._sanitize_latex(raw_stmt)
            
            # CORREÇÃO: Escapar caracteres HTML problemáticos
            statement = statement.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Imagem da questão
            q_img_raw = AdvancedPDFGenerator._get_field(q, "image")
            q_img_src = AdvancedPDFGenerator._process_question_image(q_img_raw)
            img_html = f'<img src="{q_img_src}" class="question-img" />' if q_img_src else ""
            
            # Alternativas
            alts_dict = AdvancedPDFGenerator._parse_alternatives(q)
            alts_html = ""
            if alts_dict:
                alts_items = []
                
                # Identifica a alternativa correta (para versão COM resolução)
                correct_letter = ""
                if include_resolution:
                    correct_alternative = AdvancedPDFGenerator._get_field(q, "correctAlternative", "")
                    correct_letter = AdvancedPDFGenerator._extract_correct_letter(correct_alternative)
                
                # Ordena as alternativas para garantir A, B, C, D, E
                for key in sorted(alts_dict.keys()):
                    val = alts_dict[key]
                    if val:
                        sanitized = AdvancedPDFGenerator._sanitize_latex(str(val))
                        # CORREÇÃO: Escapar HTML nas alternativas também
                        sanitized = sanitized.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        
                        if include_resolution and key.upper() == correct_letter.upper():
                            alts_items.append(f'<span class="alt-item-red">{key}) {sanitized}</span>')
                        else:
                            alts_items.append(f'<span class="alt-item">{key}) {sanitized}</span>')
                
                alts_html = f'<div class="alternativas">{" ".join(alts_items)}</div>'
            
            # Resolução (apenas na versão COM resolução)
            resolution_html = ""
            if include_resolution:
                # Busca a resolução DIRETAMENTE do objeto da questão
                # Testa VÁRIOS nomes possíveis
                raw_res = ""
                possible_fields = [
                    "detailedResolution",
                    "detailed_resolution",
                    "resolution",
                    "resolucao",
                    "solucao",
                    "answerExplanation",
                    "explanation"
                ]
                
                for field in possible_fields:
                    temp_res = AdvancedPDFGenerator._get_field(q, field, "")
                    if temp_res and temp_res.strip():
                        raw_res = temp_res
                        break
                
                if not raw_res:
                    raw_res = "Sem resolução disponível"
                    
                resolution = AdvancedPDFGenerator._sanitize_latex(raw_res)
                # CORREÇÃO CRÍTICA: Escapar HTML na resolução
                resolution = resolution.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                resolution_html = f"""
                <div class="resolucao-box">
                    <p class="resolucao-label">Solução:</p>
                    <p class="resolucao-text">{resolution}</p>
                </div>
                """
            
            # HTML da questão completa
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
        """
        Gera PDF da prova com Playwright
        Estrutura: Versão SEM resoluções + Versão COM resoluções
        """
        import time
        from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError
        
        options = options or {}
        
        # Extrai dados da prova
        fase = AdvancedPDFGenerator._get_field(exam, 'fase', '1ª FASE')
        anos_raw = AdvancedPDFGenerator._get_field(exam, 'anos', [])
        anos = anos_raw if isinstance(anos_raw, list) else [str(anos_raw)]
        year = AdvancedPDFGenerator._get_field(exam, 'ano', 2024)
        
        # Título dinâmico
        titulo = AdvancedPDFGenerator._build_exam_title(fase, anos, year)
        
        # Carrega imagens estáticas
        header_img = AdvancedPDFGenerator._load_static_img_base64("heder.PNG")
        footer_img = AdvancedPDFGenerator._load_static_img_base64("footer.PNG")
        
        # HTML das questões (2 versões)
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
        /* ========== CONFIGURAÇÃO GLOBAL ========== */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        @page {{
            size: A4 portrait;
            margin: 5mm 10mm 5mm 10mm;
        }}
        
        body {{
            font-family: 'Arial', Times, serif;
            font-size: 14pt;
            line-height: 1.4;
            color: #000;
            background: #fff;
        }}

        /* ========== ESTRUTURA: TABELA DE IMPRESSÃO ========== */
        .print-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .print-table thead {{
            display: table-header-group;
        }}
        
        .print-table tfoot {{
            display: table-footer-group;
        }}
        
        .print-table tr {{
            page-break-inside: avoid;
        }}

        /* ========== HEADER (Cabeçalho) ========== */
        .header-space {{
            width: 100%;
            text-align: center;
            margin-bottom: 2mm;
        }}

        .header-img {{
            width: 200mm;
            height: auto;
            max-width: 100%;
            margin: 0 auto;
        }}

        /* ========== FOOTER (Rodapé) ========== */
        .footer-space {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            text-align: center;
            z-index: 1000;
            margin: 0;
        }}

        .print-table tfoot td {{
            height: 30mm;
            border: none;
            vertical-align: bottom;
        }}

        .footer-img {{
            width: 160mm;
            height: auto;
            max-width: 100%;
            margin: 0 auto;
        }}

        /* ========== CONTEÚDO ========== */
        .content-wrapper {{
            width: 100%;
        }}

        .titulo-prova {{
            font-size: 14pt;
            font-weight: bold;
            margin: 0 0 1mm 33mm;
            text-align: left;
        }}

        .campos-aluno {{
            font-size: 14pt;
            margin: 0 0 5mm 8mm;
        }}

        .campos-aluno p {{
            margin-bottom: 1mm;
        }}

        /* ========== LAYOUT DE 2 COLUNAS ========== */
        .content {{
            column-count: 2;
            column-gap: 5mm;
            text-align: justify;
            margin: 0 4mm 15mm 4mm;
        }}

        .question-box {{
            break-inside: avoid;
            page-break-inside: avoid;
            margin-bottom: 2mm;
            display: inline-block;
            width: 100%;
            min-height: 20px;  /* FIX: Previne altura 0 quando LaTeX quebra */
        }}

        .enunciado {{
            font-family: 'Arial', Times, serif;
            font-size: 14pt;
            margin-bottom: 3mm;
            text-align: justify;
            line-height: 1.3;
            word-wrap: break-word;
            overflow-wrap: break-word;
            min-height: 15px;  /* FIX: Garante espaço mesmo se LaTeX quebrar */
        }}

        .question-img {{
            max-width: 100%;
            max-height: 70mm;
            display: block;
            margin: 3mm auto;
            border: 1px solid #ddd;
            padding: 1mm;
        }}

        /* Alternativas */
        .alternativas {{
            font-family: 'Arial', Times, serif;
            font-size: 14pt;
            margin-top: 1.5mm;
            margin-bottom: 1.5mm;
            display: flex;
            flex-wrap: wrap;
            gap: 6mm;
        }} 

        .alt-item {{
            white-space: nowrap;
            color: #000;
            flex-shrink: 0;
        }}

        .alt-item-red {{
            white-space: nowrap;
            color: #cc0000;
            font-weight: bold;
            flex-shrink: 0;
        }}

        /* ========== RESOLUÇÕES ========== */
        .resolucao-box {{
            margin-top: 1mm;
            margin-bottom: 5mm;
        }}

        .resolucao-label {{
            font-family: 'Arial', Times, serif;
            font-size: 14pt;
            margin-bottom: 1mm;
            color: #cc0000;
            font-weight: bold;
        }}

        .resolucao-text {{
            color: #cc0000;
            font-size: 14pt;
            line-height: 1.3;
        }}

        .titulo-resolucoes {{
            display: none;
        }}
        
        .page-break {{
            page-break-after: always;
            display: block;
            height: 1px;
        }}

        /* ========== CLASSES PARA CONTROLE DE QUEBRA ========== */
        .keep-together {{
            page-break-inside: avoid !important;
            break-inside: avoid !important;
        }}
        
        .force-break {{
            page-break-before: always !important;
            break-before: page !important;
        }}

    </style>
</head>
<body>
    <table class="print-table">
        
        <thead>
            <tr>
                <td>
                    <div class="header-space">
                        {f'<img src="{header_img}" class="header-img" />' if header_img else ''}
                    </div>
                </td>
            </tr>
        </thead>

        <tfoot>
            <tr>
                <td>
                    <div class="footer-space">
                        {f'<img src="{footer_img}" class="footer-img" />' if footer_img else ''}
                    </div>
                </td>
            </tr>
        </tfoot>

        <tbody>
            <tr>
                <td>
                    <div class="content-wrapper">
                        
                        <div class="titulo-prova">{titulo}</div>
                        <div class="campos-aluno">
                            <p><strong>ALUNO(A):</strong>___________________________________________________________________________</p>
                            <p><strong>ESCOLA:</strong> _________________________________________ <strong>MUNICÍPIO:</strong> ________________________</p>
                        </div>
                        
                        <div class="content">
                            {questions_sem_resolucao}
                        </div>

                        <div class="page-break"></div>

                        <div class="titulo-prova">{titulo}</div>
                        <div class="campos-aluno">
                            <p><strong>ALUNO(A):</strong>____________________________________________________________________________</p>
                            <p><strong>ESCOLA:</strong> _________________________________________ <strong>MUNICÍPIO:</strong> ________________________</p>
                        </div>
                        
                        <div class="content">
                            {questions_com_resolucao}
                        </div>

                    </div>
                </td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""
        
        # ========== GERAÇÃO DO PDF ==========
        buffer = io.BytesIO()
        
        for attempt in range(2):
            try:              
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        # Desempenho otimizado
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-background-networking",
                            "--disable-extensions",
                            "--disable-plugins",
                            "--disable-images"
                        ]
                    )
                    
                    page = browser.new_page()
                    
                    # Carrega HTML
                    page.set_content(html_content, wait_until="domcontentloaded", timeout=60000)
                    
                    # Aguarda MathJax (config da versão que funcionava)
                    try:
                        page.wait_for_function(
                            "typeof MathJax !== 'undefined' && MathJax.startup && MathJax.startup.promise",
                            timeout=10000
                        )
                        page.evaluate("MathJax.typesetPromise()")
                    except Exception as e:
                        logger.exception("MathJax typeset failed")
                    
                    # GERA PDF - Config da versão que funcionava (fds.text)
                    # prefer_css_page_size=True + margin 0 = @page CSS controla layout
                    pdf_bytes = page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
                    )
                    
                    # Remove blank pages
                    pdf_bytes = AdvancedPDFGenerator._remove_blank_pages(pdf_bytes)
                    
                    browser.close()
                    
                    buffer.write(pdf_bytes)
                    buffer.seek(0)
                    return buffer
                    
            except Exception as e:
                print(f"⚠️ Erro na tentativa {attempt + 1}: {e}")
                if attempt == 0:
                    time.sleep(2)
                else:
                    raise
        
        raise Exception("Não foi possível gerar o PDF")

    @staticmethod
    def create_question_bank_pdf(questions: List[Any], options: Dict[str, Any] = None) -> io.BytesIO:
        """Gera PDF do banco de questões"""
        fake_exam = {"fase": "Banco de Questões", "anos": ["Todos"], "ano": 2024}
        return AdvancedPDFGenerator.create_exam_pdf(fake_exam, questions, options)

    @staticmethod
    def create_statistical_report(data: Dict[str, Any], options: Dict[str, Any] = None) -> io.BytesIO:
        """Stub para relatórios estatísticos"""
        buffer = io.BytesIO()
        buffer.write(b"%PDF-1.4 (Report in development)")
        buffer.seek(0)
        return buffer