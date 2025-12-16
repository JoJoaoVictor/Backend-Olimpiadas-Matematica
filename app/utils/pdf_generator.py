"""Utilitários para geração de PDF."""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import tempfile
import subprocess
from io import BytesIO

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import Color, black, red, blue, green
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Image as RLImage, KeepTogether, Flowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

from app.models.exam import Exam
from app.models.question import Question
from app.core.config import settings

class AdvancedPDFGenerator:
    """Gerador avançado de PDFs."""
    
    # Configurações padrão
    DEFAULT_STYLES = {
        'title': {'fontSize': 18, 'alignment': TA_CENTER, 'spaceAfter': 20},
        'subtitle': {'fontSize': 14, 'alignment': TA_CENTER, 'spaceAfter': 15},
        'question': {'fontSize': 12, 'alignment': TA_JUSTIFY, 'spaceBefore': 15},
        'alternative': {'fontSize': 11, 'leftIndent': 20, 'spaceBefore': 5},
        'resolution': {'fontSize': 10, 'textColor': red, 'leftIndent': 10},
        'footer': {'fontSize': 9, 'alignment': TA_CENTER}
    }
    
    @staticmethod
    def create_exam_pdf(
        exam: Exam,
        questions: List[Question],
        options: Dict[str, Any] = None
    ) -> BytesIO:
        """Cria PDF da prova com opções avançadas."""
        
        options = options or {}
        
        # Configurações
        config = {
            'page_size': options.get('page_size', A4),
            'margins': options.get('margins', (20*mm, 20*mm, 25*mm, 25*mm)),
            'include_answers': options.get('include_answers', False),
            'two_columns': options.get('two_columns', False),
            'include_answer_sheet': options.get('include_answer_sheet', True),
            'watermark': options.get('watermark', None),
            'cover_info': options.get('cover_info', {}),
            'custom_header': options.get('custom_header', None),
            'custom_footer': options.get('custom_footer', None)
        }
        
        buffer = BytesIO()
        
        # Cria documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=config['page_size'],
            rightMargin=config['margins'][1],
            leftMargin=config['margins'][0], 
            topMargin=config['margins'][2],
            bottomMargin=config['margins'][3],
            title=exam.name
        )
        
        # Estilos
        styles = AdvancedPDFGenerator._create_custom_styles()
        
        # Constrói conteúdo
        story = []
        
        # Capa/Cabeçalho
        AdvancedPDFGenerator._add_cover_page(story, exam, config, styles)
        
        # Questões
        if config['two_columns']:
            AdvancedPDFGenerator._add_questions_two_columns(
                story, questions, config, styles
            )
        else:
            AdvancedPDFGenerator._add_questions_single_column(
                story, questions, config, styles
            )
        
        # Folha de respostas
        if config['include_answer_sheet'] and not config['include_answers']:
            story.append(PageBreak())
            AdvancedPDFGenerator._add_answer_sheet(story, questions, styles)
        
        # Gera PDF
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def create_question_bank_pdf(
        questions: List[Question],
        options: Dict[str, Any] = None
    ) -> BytesIO:
        """Cria PDF com banco de questões."""
        
        options = options or {}
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=25*mm,
            bottomMargin=25*mm,
            title="Banco de Questões"
        )
        
        styles = AdvancedPDFGenerator._create_custom_styles()
        story = []
        
        # Título
        story.append(Paragraph("Banco de Questões", styles['title']))
        story.append(Spacer(1, 20))
        
        # Índice (se solicitado)
        if options.get('include_index', True):
            AdvancedPDFGenerator._add_question_index(story, questions, styles)
            story.append(PageBreak())
        
        # Questões agrupadas por categoria/tema
        if options.get('group_by_category', True):
            grouped_questions = AdvancedPDFGenerator._group_questions_by_category(questions)
            
            for category, category_questions in grouped_questions.items():
                # Cabeçalho da categoria
                story.append(Paragraph(f"Categoria: {category}", styles['subtitle']))
                story.append(Spacer(1, 10))
                
                # Questões da categoria
                for question in category_questions:
                    AdvancedPDFGenerator._add_single_question(
                        story, question, styles, include_resolution=True
                    )
                    story.append(Spacer(1, 15))
                
                story.append(PageBreak())
        else:
            # Questões em ordem sequencial
            for i, question in enumerate(questions, 1):
                AdvancedPDFGenerator._add_single_question(
                    story, question, styles, question_number=i, include_resolution=True
                )
                story.append(Spacer(1, 15))
        
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def create_statistical_report(
        data: Dict[str, Any],
        options: Dict[str, Any] = None
    ) -> BytesIO:
        """Cria relatório estatístico."""
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = AdvancedPDFGenerator._create_custom_styles()
        story = []
        
        # Título
        story.append(Paragraph("Relatório Estatístico", styles['title']))
        story.append(Spacer(1, 20))
        
        # Estatísticas gerais
        if 'general_stats' in data:
            story.append(Paragraph("Estatísticas Gerais", styles['subtitle']))
            stats_data = [
                ['Métrica', 'Valor'],
                ['Total de Questões', data['general_stats'].get('total_questions', 0)],
                ['Total de Provas', data['general_stats'].get('total_exams', 0)],
                ['Total de Usuários', data['general_stats'].get('total_users', 0)],
            ]
            
            stats_table = Table(stats_data, colWidths=[8*cm, 4*cm])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), Color(0.8, 0.8, 0.8)),
                ('TEXTCOLOR', (0, 0), (-1, 0), black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 1), (-1, -1), Color(0.95, 0.95, 0.95)),
                ('GRID', (0, 0), (-1, -1), 1, black)
            ]))
            
            story.append(stats_table)
            story.append(Spacer(1, 20))
        
        # Gráficos (se fornecidos)
        if 'charts' in data:
            for chart_data in data['charts']:
                story.append(Paragraph(chart_data['title'], styles['subtitle']))
                # TODO: Integrar com matplotlib para gerar gráficos
                story.append(Spacer(1, 20))
        
        doc.build(story)
        buffer.seek(0)
        
        return buffer
    
    @staticmethod
    def _create_custom_styles():
        """Cria estilos customizados."""
        styles = getSampleStyleSheet()
        
        # Estilo para título principal
        styles.add(ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=Color(0, 0, 0.8)
        ))
        
        # Estilo para subtítulo
        styles.add(ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=15,
            textColor=Color(0, 0, 0.6)
        ))
        
        # Estilo para questões
        styles.add(ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=12,
            alignment=TA_JUSTIFY,
            spaceBefore=15,
            spaceAfter=8,
            leftIndent=0,
            rightIndent=0
        ))
        
        # Estilo para alternativas
        styles.add(ParagraphStyle(
            'Alternative',
            parent=styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceBefore=3,
            spaceAfter=3
        ))
        
        # Estilo para resolução
        styles.add(ParagraphStyle(
            'Resolution',
            parent=styles['Normal'],
            fontSize=10,
            textColor=red,
            leftIndent=15,
            spaceBefore=8,
            spaceAfter=12,
            backColor=Color(1, 0.95, 0.95)
        ))
        
        return styles
    
    @staticmethod
    def _add_cover_page(story, exam, config, styles):
        """Adiciona página de capa."""
        
        # Logo/Header customizado
        if config.get('custom_header'):
            story.append(Paragraph(config['custom_header'], styles['CustomTitle']))
            story.append(Spacer(1, 20))
         
        # Título da prova
        story.append(Paragraph(exam.name, styles['CustomTitle']))
        story.append(Spacer(1, 30))
        
        # Informações da prova em tabela
        info_data = [
            ['Fase:', exam.fase],
            ['Anos/Séries:', ', '.join(exam.anos)],
            ['Total de Questões:', str(exam.total_questions)],
            ['Status:', exam.status.value]
        ]
        
        if exam.estimated_duration:
            info_data.append(['Tempo Estimado:', f"{exam.estimated_duration} minutos"])
        
        info_table = Table(info_data, colWidths=[5*cm, 8*cm])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 40))
        
        # Campos para preenchimento do estudante
        cover_info = config.get('cover_info', {})
        if cover_info or True:  # Sempre inclui campos básicos
            student_data = [
                ['Nome do Estudante:', '_' * 60],
                ['Escola/Instituição:', '_' * 60],
                ['Turma/Série:', '_' * 30],
                ['Data:', '_' * 20],
            ]
            
            student_table = Table(student_data, colWidths=[4*cm, 12*cm])
            student_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(student_table)
            story.append(Spacer(1, 30))
        
        # Instruções
        instructions = """
        <b>INSTRUÇÕES:</b><br/>
        • Leia atentamente cada questão antes de responder<br/>
        • Marque apenas uma alternativa para cada questão<br/>
        • Use caneta azul ou preta<br/>
        • Não é permitido o uso de calculadora<br/>
        • Duração da prova conforme indicado acima
        """
        
        story.append(Paragraph(instructions, styles['Normal']))
        story.append(PageBreak())
    
    @staticmethod
    def _add_questions_single_column(story, questions, config, styles):
        """Adiciona questões em coluna única."""
        
        for i, question in enumerate(questions, 1):
            # Mantém questão junta na mesma página
            question_content = []
            
            # Enunciado com numeração
            question_text = f"<b>{i}. {question.question_statement}</b>"
            question_content.append(Paragraph(question_text, styles['Question']))
            
            # Imagem (se houver)
            if question.image:
                try:
                    img_path = Path(settings.UPLOAD_PATH) / question.image.file_path
                    if img_path.exists():
                        img = RLImage(str(img_path), width=12*cm, height=8*cm)
                        question_content.append(img)
                        question_content.append(Spacer(1, 10))
                except:
                    pass
            
            # Fórmula LaTeX renderizada
            if question.rendered_formula_url:
                try:
                    formula_path = Path(settings.STATIC_PATH) / question.rendered_formula_url.lstrip('/')
                    if formula_path.exists():
                        formula_img = RLImage(str(formula_path), width=10*cm, height=3*cm)
                        question_content.append(formula_img)
                        question_content.append(Spacer(1, 10))
                except:
                    pass
            
            # Alternativas
            alternatives = AdvancedPDFGenerator._parse_alternatives(question.alternatives)
            for alt in alternatives:
                question_content.append(Paragraph(alt, styles['Alternative']))
            
            # Espaço para resposta (se não incluir gabarito)
            if not config['include_answers']:
                question_content.append(Spacer(1, 15))
            
            # Resolução (se solicitada)
            if config['include_answers']:
                question_content.append(Spacer(1, 10))
                question_content.append(Paragraph("<b>Resolução:</b>", styles['Resolution']))
                question_content.append(Paragraph(question.detailed_resolution, styles['Resolution']))
                question_content.append(Paragraph(
                    f"<b>Resposta: {question.correct_alternative.upper()}</b>", 
                    styles['Resolution']
                ))
            
            # Adiciona questão como bloco
            story.append(KeepTogether(question_content))
            story.append(Spacer(1, 20))
    
    @staticmethod
    def _add_questions_two_columns(story, questions, config, styles):
        """Adiciona questões em duas colunas."""
        # TODO: Implementar layout em duas colunas
        # Por enquanto, usa coluna única
        AdvancedPDFGenerator._add_questions_single_column(story, questions, config, styles)
    
    @staticmethod
    def _add_single_question(story, question, styles, question_number=None, include_resolution=False):
        """Adiciona uma única questão."""
        
        if question_number:
            question_text = f"<b>Questão {question_number}: {question.name}</b>"
        else:
            question_text = f"<b>{question.name}</b>"
        
        story.append(Paragraph(question_text, styles['Question']))
        
        # Metadados da questão
        metadata = f"""
        <i>Série: {question.serie_ano} | Dificuldade: {question.difficulty_level.value}/5 | 
        Tema: {question.bncc_theme} | Código: {question.ability_code}</i>
        """
        story.append(Paragraph(metadata, styles['Normal']))
        story.append(Spacer(1, 8))
        
        # Enunciado
        story.append(Paragraph(question.question_statement, styles['Normal']))
        
        # Alternativas
        alternatives = AdvancedPDFGenerator._parse_alternatives(question.alternatives)
        for alt in alternatives:
            story.append(Paragraph(alt, styles['Alternative']))
        
        # Resolução
        if include_resolution:
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Resolução:</b>", styles['Resolution']))
            story.append(Paragraph(question.detailed_resolution, styles['Resolution']))
            story.append(Paragraph(
                f"<b>Resposta: {question.correct_alternative.upper()}</b>", 
                styles['Resolution']
            ))
    
    @staticmethod
    def _add_answer_sheet(story, questions, styles):
        """Adiciona folha de respostas."""
        
        story.append(Paragraph("<b>FOLHA DE RESPOSTAS</b>", styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Instruções
        instructions = "Preencha completamente o círculo da alternativa escolhida:"
        story.append(Paragraph(instructions, styles['Normal']))
        story.append(Spacer(1, 15))
        
        # Grid de respostas
        num_questions = len(questions)
        rows_per_column = 25
        num_columns = (num_questions + rows_per_column - 1) // rows_per_column
        
        for col in range(num_columns):
            start_q = col * rows_per_column + 1
            end_q = min(start_q + rows_per_column - 1, num_questions)
            
            answer_data = [['Questão', 'A', 'B', 'C', 'D', 'E']]
            
            for q_num in range(start_q, end_q + 1):
                row = [str(q_num)] + ['○'] * 5
                answer_data.append(row)
            
            answer_table = Table(answer_data, colWidths=[1.5*cm] + [1*cm]*5)
            answer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), Color(0.8, 0.8, 0.8)),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(answer_table)
            
            if col < num_columns - 1:
                story.append(Spacer(1, 20))
    
    @staticmethod
    def _add_question_index(story, questions, styles):
        """Adiciona índice de questões."""
        
        story.append(Paragraph("Índice de Questões", styles['CustomSubtitle']))
        story.append(Spacer(1, 15))
        