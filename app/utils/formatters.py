"""
═══════════════════════════════════════════════════════════════
ARQUIVO: app/utils/formatters.py
PROPÓSITO: Formatadores de dados para padrão brasileiro
TIPO: Funções puras - NÃO acessa banco de dados
USO: Formatar dados para exibição ao usuário
═══════════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import re
import json # <--- ADICIONADO
from decimal import Decimal
  

class DataFormatters:
    """
    Classe de formatadores de dados.
    
    IMPORTANTE:
    - Converte dados técnicos em formato legível
    - Padrão brasileiro (dd/mm/yyyy, R$, etc)
    - Apenas formatação visual, não altera dados
    - Funções puras e stateless
    """
    
    # ═════════════════════════════════════════════════════════
    # FORMATADORES DE DATA E HORA
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_datetime_br(dt: datetime, include_seconds: bool = False) -> str:
        """
        Formata data e hora para padrão brasileiro.
        """
        if not dt:
            return ""
        
        try:
            if include_seconds:
                return dt.strftime("%d/%m/%Y às %H:%M:%S")
            else:
                return dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            return str(dt)
    
    @staticmethod
    def format_date_br(dt: datetime) -> str:
        """Formata apenas a data para padrão brasileiro."""
        if not dt: return ""
        try:
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return str(dt)
    
    @staticmethod
    def format_time_br(dt: datetime, include_seconds: bool = True) -> str:
        """Formata apenas o horário."""
        if not dt: return ""
        try:
            if include_seconds:
                return dt.strftime("%H:%M:%S")
            else:
                return dt.strftime("%H:%M")
        except Exception:
            return str(dt)
    
    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """Formata tempo relativo em português (ex: há 2 horas)."""
        if not dt: return ""
        
        now = datetime.utcnow()
        diff = now - dt
        seconds = diff.total_seconds()
        
        if seconds < 60: return "agora"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"há {hours} hora{'s' if hours != 1 else ''}"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"há {days} dia{'s' if days != 1 else ''}"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"há {weeks} semana{'s' if weeks != 1 else ''}"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"há {months} mês{'es' if months != 1 else ''}"
        else:
            years = int(seconds / 31536000)
            return f"há {years} ano{'s' if years != 1 else ''}"
    
    @staticmethod
    def format_duration(minutes: int) -> str:
        """Formata duração em minutos para texto legível (ex: 1h 30min)."""
        if not minutes or minutes <= 0:
            return "Não especificado"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if hours > 0:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}min"
            return f"{hours}h"
        return f"{remaining_minutes}min"
    
    
    # ═════════════════════════════════════════════════════════
    # FORMATADORES NUMÉRICOS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_number_br(number: Union[int, float, Decimal], decimals: int = 2) -> str:
        """Formata número para padrão brasileiro (1.234,56)."""
        if number is None: return "0"
        try:
            num = float(number)
            formatted = f"{num:,.{decimals}f}"
            formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
            return formatted
        except Exception:
            return str(number)
    
    @staticmethod
    def format_currency_br(value: Union[int, float, Decimal]) -> str:
        """Formata valor monetário brasileiro (R$ 1.234,56)."""
        if value is None: value = 0
        formatted = DataFormatters.format_number_br(value, decimals=2)
        return f"R$ {formatted}"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """Formata porcentagem (85,5%)."""
        if value is None: return "0%"
        try:
            formatted = f"{value:.{decimals}f}".replace('.', ',')
            return f"{formatted}%"
        except Exception:
            return "0%"
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Formata tamanho de arquivo (MB, GB)."""
        if size_bytes == 0: return "0 B"
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.1f} {units[unit_index]}"
    
    
    # ═════════════════════════════════════════════════════════
    # FORMATADORES ESPECÍFICOS DO SISTEMA
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_difficulty_level(level: int) -> Dict[str, Any]:
        """Formata nível de dificuldade com detalhes visuais."""
        difficulty_map = {
            1: {"name": "Muito Fácil", "color": "#28a745", "emoji": "😊"},
            2: {"name": "Fácil", "color": "#6c757d", "emoji": "🙂"},
            3: {"name": "Médio", "color": "#ffc107", "emoji": "😐"},
            4: {"name": "Difícil", "color": "#fd7e14", "emoji": "😰"},
            5: {"name": "Muito Difícil", "color": "#dc3545", "emoji": "😱"}
        }
        return difficulty_map.get(level, {"name": f"Nível {level}", "color": "#6c757d", "emoji": "❓"})
    
    @staticmethod
    def format_school_years(years: List[str]) -> str:
        """Formata lista de anos escolares em texto."""
        if not years: return "Não especificado"
        if len(years) == 1: return years[0]
        if len(years) == 2: return f"{years[0]} e {years[1]}"
        return ", ".join(years[:-1]) + f" e {years[-1]}"
    
    @staticmethod
    def format_question_preview(statement: str, max_length: int = 100) -> str:
        """Formata preview do enunciado da questão."""
        if not statement: return ""
        clean = re.sub(r'<[^>]+>', '', statement)
        clean = ' '.join(clean.split())
        if len(clean) <= max_length: return clean
        truncated = clean[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:
            truncated = truncated[:last_space]
        return truncated + "..."
    
    @staticmethod
    def extract_alternatives_text(alternatives: Union[str, List, Dict]) -> List[str]:
        """
        NOVO: Extrai apenas o texto das alternativas de forma robusta.
        Ideal para geração de PDF e correção de bugs de parse.
        
        Lida com:
        - JSON strings
        - Listas Python
        - Texto formatado: "a) Opção 1 b) Opção 2"
        - Texto com vírgulas: "A) 1, B) 2"
        """
        if not alternatives:
            return []
            
        # 1. Se já for objeto Python
        if isinstance(alternatives, list):
            return [str(x) for x in alternatives]
        if isinstance(alternatives, dict):
            return list(alternatives.values())

        text = str(alternatives).strip()

        # 2. Tenta JSON
        try:
            if text.startswith(('{', '[')):
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return list(parsed.values())
                if isinstance(parsed, list):
                    return parsed
        except json.JSONDecodeError:
            pass

        # 3. Regex Robusto (O mesmo da correção sugerida anteriormente)
        # Divide em (letra + parentese/ponto) ignorando vírgulas anteriores
        pattern = r'(?:^|\s|,)[a-eA-E][).]\s*'
        parts = re.split(pattern, text)
        
        # Limpa resultados
        cleaned = [p.strip().rstrip(',') for p in parts if p and p.strip()]
        
        # Fallback: se o regex falhou mas tem texto, retorna o texto inteiro
        if not cleaned and text:
            return [text]
            
        return cleaned

    @staticmethod
    def format_alternatives_list(alternatives: Union[str, List, Dict]) -> List[Dict[str, str]]:
        """
        Formata alternativas em lista estruturada para o Frontend.
        
        ATUALIZADO: Agora usa extract_alternatives_text para ser mais robusto
        contra erros de formatação.
        """
        # Usa o método robusto para pegar os textos
        texts = DataFormatters.extract_alternatives_text(alternatives)
        
        letters = ['A', 'B', 'C', 'D', 'E']
        formatted = []
        
        for i, text in enumerate(texts):
            if i < 5: # Garante max 5 alternativas
                letter = letters[i]
                formatted.append({
                    'letter': letter,
                    'content': text,
                    'full': f"{letter}) {text}"
                })
        
        return formatted
    
    @staticmethod
    def format_user_role(role: str) -> Dict[str, str]:
        """Formata role do usuário com detalhes visuais."""
        role_map = {
            'ADMIN': {'name': 'Administrador', 'color': '#dc3545', 'icon': '👑'},
            'PROFESSOR': {'name': 'Professor', 'color': '#007bff', 'icon': '👨‍🏫'},
            'STUDENT': {'name': 'Estudante', 'color': '#28a745', 'icon': '👨‍🎓'}
        }
        return role_map.get(role.upper(), {'name': role, 'color': '#6c757d', 'icon': '👤'})
    
    @staticmethod
    def format_exam_status(status: str) -> Dict[str, str]:
        """Formata status da prova com detalhes visuais."""
        status_map = {
            'PENDENTE': {'name': 'Pendente', 'color': '#ffc107', 'icon': '⏳'},
            'APLICADA': {'name': 'Aplicada', 'color': '#17a2b8', 'icon': '✅'},
            'APROVADA': {'name': 'Aprovada', 'color': '#28a745', 'icon': '🎉'}
        }
        return status_map.get(status.upper(), {'name': status, 'color': '#6c757d', 'icon': '❓'})
    
    @staticmethod
    def format_cpf(cpf: str) -> str:
        """Formata CPF (123.456.789-00)."""
        if not cpf: return ""
        cpf_clean = re.sub(r'\D', '', cpf)
        if len(cpf_clean) != 11: return cpf
        return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}"
    
    @staticmethod
    def format_phone_br(phone: str) -> str:
        """Formata telefone ((11) 99999-9999)."""
        if not phone: return ""
        phone_clean = re.sub(r'\D', '', phone)
        if len(phone_clean) == 11:
            return f"({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:]}"
        elif len(phone_clean) == 10:
            return f"({phone_clean[:2]}) {phone_clean[2:6]}-{phone_clean[6:]}"
        else:
            return phone

    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Trunca texto mantendo palavras inteiras."""
        if not text or len(text) <= max_length: return text
        truncated = text[:max_length - len(suffix)]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:
            truncated = truncated[:last_space]
        return truncated + suffix