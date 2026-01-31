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
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


class AdvancedPDFGenerator:
    
    @staticmethod
    def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
        """Acessa campos de forma segura (dict ou objeto)"""
        if isinstance(obj, dict):
            return obj.get(field_name, default)
        return getattr(obj, field_name, default)

    @staticmethod
    def _sanitize_latex(text: str) -> str:
        """
        Normaliza strings LaTeX do banco
        Converte escapes duplos (\\\\) para simples (\\)
        """
        if not text:
            return ""
        return text.replace('\\\\', '\\')

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
        Extrai alternativas e retorna dict limpo
        Retorna: {"a": "texto", "b": "texto", ...}
        """
        alternatives_raw = AdvancedPDFGenerator._get_field(question, "alternatives")
        
        if isinstance(alternatives_raw, dict):
            return alternatives_raw
        
        if isinstance(alternatives_raw, str):
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
                    return loaded
                elif isinstance(loaded, str):
                    # Se for string, tenta parse novamente
                    try:
                        return json.loads(loaded)
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
                return {key.upper(): value.strip() for key, value in matches}
        
        return {}

    @staticmethod
    def _extract_correct_letter(correct_alternative: str) -> str:
        """
        Extrai a letra da alternativa correta do formato do banco
        Exemplos: 
        - "e) 1200" -> "E"
        - "B) 4" -> "B"
        - "c) 8" -> "C"
        - " b) 42" -> "B"
        - "DE quem mais usa somente celular" -> "" (sem letra)
        """
        if not correct_alternative:
            return ""
        
        # Remove espaços no início e fim
        text = correct_alternative.strip()
        
        # Padrão 1: letra seguida de ) ou .
        # Ex: "e) 1200", "B) 4", "c) 8", "a."
        match = re.match(r'^([A-Ea-e])[\)\.]', text)
        if match:
            return match.group(1).upper()
        
        # Padrão 2: apenas a letra no início (pode ter espaço após)
        # Ex: "a 1200", "B 4"
        match = re.match(r'^([A-Ea-e])\b', text)
        if match:
            return match.group(1).upper()
        
        # Padrão 3: letra entre parênteses
        # Ex: "(e) 1200", "(B) 4"
        match = re.match(r'^\(([A-Ea-e])\)', text)
        if match:
            return match.group(1).upper()
        
        return ""

    @staticmethod
    def _render_questions_html(questions: List[Any], include_resolution: bool = False) -> str:
        """
        Renderiza HTML das questões
        - SEM resolução: todas as alternativas normais (em preto)
        - COM resolução: todas as alternativas, com a correta em vermelho + resolução
        """
        html_parts = []
        
        for i, q in enumerate(questions, 1):
            # DEBUG: Verificar TODOS os campos da questão
            # Enunciado (sempre preto)
            raw_stmt = (
                AdvancedPDFGenerator._get_field(q, "question_statement") or
                AdvancedPDFGenerator._get_field(q, "questionStatement", "")
            )
            statement = AdvancedPDFGenerator._sanitize_latex(raw_stmt)
            
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
                        
                        if include_resolution and key.upper() == correct_letter.upper():
                            # Na versão COM resolução: alternativa correta em vermelho
                            alts_items.append(f'<span class="alt-item-red">{key}) {sanitized}</span>')
                        else:
                            # Na versão SEM resolução: todas em preto
                            # Na versão COM resolução: alternativas incorretas em preto
                            alts_items.append(f'<span class="alt-item">{key}) {sanitized}</span>')
                
                alts_html = f'<div class="alternativas">{" ".join(alts_items)}</div>'
            
            # Resolução (apenas na versão COM resolução) - TEXTO VERMELHO
            resolution_html = ""
            if include_resolution:
                # Busca a resolução DIRETAMENTE do objeto da questão
                # Testa VÁRIOS nomes possíveis
                raw_res = ""
                
                # Lista de possíveis nomes de campo
                possible_fields = [
                    "detailedResolution",  # camelCase do payload
                    "detailed_resolution", # snake_case do banco
                    "resolution",          # nome alternativo
                    "resolucao",           # em português
                    "solucao",             # outro nome em português
                    "answerExplanation",   # explicação da resposta
                    "explanation"          # explicação
                ]
                
                for field in possible_fields:
                    temp_res = AdvancedPDFGenerator._get_field(q, field, "")
                    if temp_res and temp_res.strip():
                        raw_res = temp_res
                        break
                
                if not raw_res:
                    raw_res = "Sem resolução disponível"
                    
                resolution = AdvancedPDFGenerator._sanitize_latex(raw_res)
                
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
                <title>Prova UNEMAT </title>
                
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
                    
                    /* Configuração da página e margens */
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
                    
                    .print-table thead {{ display: table-header-group; }}
                    .print-table tfoot {{ display: table-footer-group; }}
                    .print-table tr {{ page-break-inside: avoid; }}

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

                    /* ========== FOOTER (Rodapé) - CORREÇÃO APLICADA ========== */
                    /* 1. O conteúdo do rodapé (imagem) agora é fixo no bottom */
                    .footer-space {{
                        position: fixed;   /* Força a ficar na tela, independente da tabela */
                        bottom: 0;         /* Cola no fundo da área de margem */
                        left: 0;
                        width: 100%;
                        text-align: center;
                        z-index: 1000;
                        margin: 0;         /* Remove margens para calcular exato */
                    }}

                    /* 2. A célula do tfoot serve apenas para RESERVAR ESPAÇO no fluxo do texto.
                          Isso impede que as questões desçam até o fundo e fiquem atrás da imagem do rodapé. */
                    .print-table tfoot td {{
                        height: 30mm;      /* Altura reservada (ajuste conforme a altura da sua img) */
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
                    }}

                    .enunciado {{
                        font-family: 'Arial', Times, serif;
                        font-size: 14pt;
                        margin-bottom: 3mm;
                        text-align: justify;
                        line-height: 1.3;
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
        
        # ========== GERAÇÃO DO PDF VIA PLAYWRIGHT ==========
        buffer = io.BytesIO()
        
        max_retries = 2
        for attempt in range(max_retries):
            try:              
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",  # Reduz uso de memória
                            "--disable-gpu"
                        ]
                    )
                    
                    page = browser.new_page()
                    
                    # Carrega HTML
                    page.set_content(html_content, wait_until="domcontentloaded", timeout=60000)
                    
                    # Aguarda MathJax (reduzido para 10 segundos)
                    try:
                        page.wait_for_function(
                            "typeof MathJax !== 'undefined' && MathJax.startup && MathJax.startup.promise",
                            timeout=10000
                        )
                        page.evaluate("MathJax.typesetPromise()")
                    except Exception as e:
                        print(f"⚠️ MathJax timeout (continuando): {e}")
                    
                    # Gera PDF (SEM PARÂMETRO TIMEOUT)
                    pdf_bytes = page.pdf(
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
                    )
                    
                    browser.close()
                    
                    # Sucesso
                    buffer.write(pdf_bytes)
                    buffer.seek(0)
                    return buffer
                    
            except PlaywrightTimeoutError as e:
                print(f"⚠️ Timeout na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"⚠️ Tentando novamente em 2 segundos...")
                    time.sleep(2)
                else:
                    raise
            except Exception as e:
                print(f"⚠️ Erro na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"⚠️ Tentando novamente em 2 segundos...")
                    time.sleep(2)
                else:
                    raise
        
        raise Exception("Não foi possível gerar o PDF após múltiplas tentativas")

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