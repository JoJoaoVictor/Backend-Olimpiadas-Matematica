"""Serviços de renderização LaTeX."""

import os
import uuid
from typing import Optional
import tempfile
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationException


class LaTeXService:
    """Serviços de LaTeX."""
    
    LATEX_TEMPLATE = r"""
\documentclass[12pt]{{standalone}}
\usepackage{{amsmath,amsfonts,amssymb}}
\usepackage{{xcolor}}
\begin{{document}}
${content}$
\end{{document}}
"""
    
    @staticmethod
    def validate_latex(latex_code: str) -> bool:
        """Valida código LaTeX básico."""
        if not latex_code or not latex_code.strip():
            return False
        
        # Validações básicas de segurança
        forbidden_commands = [
            '\\input', '\\include', '\\write', '\\open', '\\read',
            '\\immediate', '\\shell', '\\system', '\\execute',
            '\\def', '\\let', '\\expandafter'
        ]
        
        for cmd in forbidden_commands:
            if cmd in latex_code:
                raise ValidationException(f"Comando LaTeX não permitido: {cmd}")
        
        return True
    
    @staticmethod
    def render_to_png(latex_code: str) -> Optional[str]:
        """Renderiza LaTeX para PNG."""
        try:
            # Valida código
            LaTeXService.validate_latex(latex_code)
            
            # Cria arquivo temporário
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Nome único para o arquivo
                filename = f"latex_{uuid.uuid4().hex}"
                tex_file = temp_path / f"{filename}.tex"
                
                # Cria arquivo LaTeX
                latex_content = LaTeXService.LATEX_TEMPLATE.replace('${content}', latex_code)
                tex_file.write_text(latex_content, encoding='utf-8')
                
                # Compila LaTeX para DVI
                result = subprocess.run([
                    'latex', 
                    '-interaction=nonstopmode',
                    '-output-directory', str(temp_path),
                    str(tex_file)
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    raise ValidationException(f"Erro na compilação LaTeX: {result.stderr}")
                
                # Converte DVI para PNG
                dvi_file = temp_path / f"{filename}.dvi"
                png_file = temp_path / f"{filename}.png"
                
                result = subprocess.run([
                    'dvipng',
                    '-T', 'tight',
                    '-D', '300',  # DPI
                    '-bg', 'transparent',
                    '-o', str(png_file),
                    str(dvi_file)
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    raise ValidationException(f"Erro na conversão para PNG: {result.stderr}")
                
                # Move arquivo para diretório estático
                static_dir = Path(settings.STATIC_PATH) / "latex"
                static_dir.mkdir(parents=True, exist_ok=True)
                
                final_filename = f"{uuid.uuid4().hex}.png"
                final_path = static_dir / final_filename
                
                png_file.rename(final_path)
                
                # Retorna URL relativa
                return f"/static/latex/{final_filename}"
                
        except subprocess.TimeoutExpired:
            raise ValidationException("Timeout na renderização LaTeX")
        except Exception as e:
            raise ValidationException(f"Erro na renderização LaTeX: {str(e)}")
         
        return None
    
    @staticmethod
    def render_to_svg(latex_code: str) -> Optional[str]:
        """Renderiza LaTeX para SVG (alternativa ao PNG)."""
        try:
            # TODO: Implementar renderização para SVG usando dvisvgm
            # Similar ao PNG mas usando dvisvgm em vez de dvipng
            pass
        except Exception as e:
            raise ValidationException(f"Erro na renderização SVG: {str(e)}")
        
        return None

