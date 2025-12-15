"""Serviços de geração de PDF."""

from typing import List, Optional, Dict, Any
from io import BytesIO
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Image as RLImage, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas


from app.models.exam import Exam
from app.models.question import Question
from app.schemas.exam import ExamPDFRequest
from app.core.config import settings


class PDFService:
    """Serviços de geração de PDF."""
    
    @staticmethod
    def generate_exam_pdf(
        exam: Exam,
        questions: List[Question],
        pdf_request: ExamPDFRequest,
        output_path: Optional[str] = None
    ) -> BytesIO:
        """Gera PDF da prova."""
        
        # Buffer para o PDF
        buffer = BytesIO()
        
        # Configuração do documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=25*mm,
            bottomMargin=25*mm,
            title=exam.name
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilo personalizado para título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        # Estilo para questões
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceBefore=12,
            spaceAfter=6
        )
        
        # Estilo para alternativas
        alternative_style = ParagraphStyle(
            'Alternative',
            parent=styles['Normal'],
            fontSize=10,
            leftIndent=20,
            spaceBefore=3
        )
        
        # Estilo para resolução
        resolution_style = ParagraphStyle(
            'Resolution',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            leftIndent=10,
            spaceBefore=6,
            spaceAfter=12
        )
        
        story = []
        
        # Cabeçalho da prova
        PDFService._add_exam_header(story, exam, pdf_request.cover_info, title_style, styles)
        
        # Questões
        PDFService._add_questions(
            story, 
            questions, 
            pdf_request.include_answers,
            question_style,
            alternative_style,
            resolution_style
        )
        
        # Se inclui respostas, adiciona página de gabarito
        if pdf_request.include_answers:
            story.append(PageBreak())
            PDFService._add_answer_sheet(story, questions, styles)
        
        # Gera PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def _add_exam_header(
        story: List,
        exam: Exam,
        cover_info: Optional[Dict[str, Any]],
        title_style: ParagraphStyle,
        styles: Dict
    ):
        """Adiciona cabeçalho da prova."""
        
        # Logo/Cabeçalho da instituição
        if cover_info and cover_info.get('logo_path'):
            try:
                logo = RLImage(cover_info['logo_path'], width=150, height=40)
                story.append(logo)
                story.append(Spacer(1, 10))
            except:
                pass  # Logo não encontrada, pula
        
        # Título da prova
        story.append(Paragraph(exam.name, title_style))
        
        # Informações da prova
        info_data = [
            ['Fase:', exam.fase],
            ['Anos:', ', '.join(exam.anos)],
            ['Status:', exam.status.value],
        ]
         
        if exam.estimated_duration:
            info_data.append(['Duração:', f"{exam.estimated_duration} minutos"])
        
        info_table = Table(info_data, colWidths=[30*mm, 80*mm])
        info_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Campos para preenchimento do aluno
        if cover_info:
            student_fields = [
                ['Nome:', '_' * 80],
                ['Escola:', '_' * 60],
                ['Turma:', '_' * 20],
            ]
            
            student_table = Table(student_fields, colWidths=[20*mm, 120*mm])
            student_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(student_table)
            story.append(Spacer(1, 30))
    
    @staticmethod
    def _add_questions(
        story: List,
        questions: List[Question],
        include_answers: bool,
        question_style: ParagraphStyle,
        alternative_style: ParagraphStyle,
        resolution_style: ParagraphStyle
    ):
        """Adiciona questões ao PDF."""
        
        for i, question in enumerate(questions, 1):
            # Número e enunciado da questão
            question_text = f"<b>{i}) {question.question_statement}</b>"
            story.append(Paragraph(question_text, question_style))
            
            # Imagem da questão (se houver)
            if question.image and question.image.file_path:
                try:
                    img_path = Path(settings.UPLOAD_PATH) / question.image.file_path
                    if img_path.exists():
                        img = RLImage(str(img_path), width=120, height=80)
                        story.append(img)
                        story.append(Spacer(1, 6))
                except:
                    pass  # Imagem não encontrada
            
            # Fórmula LaTeX renderizada (se houver)
            if question.rendered_formula_url:
                try:
                    formula_path = Path(settings.STATIC_PATH) / question.rendered_formula_url.lstrip('/')
                    if formula_path.exists():
                        formula_img = RLImage(str(formula_path), width=100, height=40)
                        story.append(formula_img)
                        story.append(Spacer(1, 6))
                except:
                    pass
            
            # Alternativas
            alternatives = PDFService._parse_alternatives(question.alternatives)
            for alt in alternatives:
                story.append(Paragraph(alt, alternative_style))
            
            story.append(Spacer(1, 10))
            
            # Resolução (se solicitada)
            if include_answers:
                story.append(Paragraph("<b>Resolução:</b>", resolution_style))
                story.append(Paragraph(question.detailed_resolution, resolution_style))
                story.append(Paragraph(f"<b>Resposta correta: {question.correct_alternative.upper()}</b>", resolution_style))
                story.append(Spacer(1, 15))
    
    @staticmethod
    def _add_answer_sheet(story: List, questions: List[Question], styles: Dict):
        """Adiciona folha de gabarito."""
        story.append(Paragraph("<b>GABARITO</b>", styles['Title']))
        story.append(Spacer(1, 20))
        
        # Tabela de gabarito
        gabarito_data = [['Questão', 'Resposta']]
        
        for i, question in enumerate(questions, 1):
            gabarito_data.append([str(i), question.correct_alternative.upper()])
        
        gabarito_table = Table(gabarito_data, colWidths=[40*mm, 40*mm])
        gabarito_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(gabarito_table)
    
    @staticmethod
    def _parse_alternatives(alternatives_text: str) -> List[str]:
        """Extrai alternativas do texto."""
        import re
        
        # Regex para capturar alternativas a), b), c), d), e)
        pattern = r'([a-e]\)\s*[^a-e]*?)(?=[a-e]\)|$)'
        matches = re.findall(pattern, alternatives_text, re.IGNORECASE | re.DOTALL)
        
        if matches:
            return [alt.strip() for alt in matches]
        
        # Fallback: divide por letras
        alternatives = []
        for letter in ['a)', 'b)', 'c)', 'd)', 'e)']:
            if letter in alternatives_text.lower():
                start = alternatives_text.lower().find(letter)
                # Encontra próxima alternativa ou fim
                next_letters = [l for l in ['a)', 'b)', 'c)', 'd)', 'e)'] if l != letter]
                end = len(alternatives_text)
                
                for next_letter in next_letters:
                    next_pos = alternatives_text.lower().find(next_letter, start + 1)
                    if next_pos != -1 and next_pos < end:
                        end = next_pos
                
                alt_text = alternatives_text[start:end].strip()
                if alt_text:
                    alternatives.append(alt_text)
        
        return alternatives if alternatives else [alternatives_text]

