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
        
        FORMATO: dd/mm/yyyy às HH:MM ou dd/mm/yyyy às HH:MM:SS
        
        Args:
            dt: Objeto datetime
            include_seconds: Se True, inclui segundos
            
        Returns:
            String formatada ou "" se dt for None
            
        Exemplos:
            >>> from datetime import datetime
            >>> dt = datetime(2025, 10, 2, 14, 30, 45)
            >>> DataFormatters.format_datetime_br(dt)
            '02/10/2025 às 14:30'
            
            >>> DataFormatters.format_datetime_br(dt, include_seconds=True)
            '02/10/2025 às 14:30:45'
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
        """
        Formata apenas a data para padrão brasileiro.
        
        FORMATO: dd/mm/yyyy
        
        Args:
            dt: Objeto datetime
            
        Returns:
            String formatada ou "" se dt for None
            
        Exemplos:
            >>> from datetime import datetime
            >>> dt = datetime(2025, 10, 2)
            >>> DataFormatters.format_date_br(dt)
            '02/10/2025'
        """
        if not dt:
            return ""
        
        try:
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return str(dt)
    
    
    @staticmethod
    def format_time_br(dt: datetime, include_seconds: bool = True) -> str:
        """
        Formata apenas o horário.
        
        FORMATO: HH:MM ou HH:MM:SS
        
        Args:
            dt: Objeto datetime
            include_seconds: Se True, inclui segundos
            
        Returns:
            String formatada ou "" se dt for None
            
        Exemplos:
            >>> from datetime import datetime
            >>> dt = datetime(2025, 10, 2, 14, 30, 45)
            >>> DataFormatters.format_time_br(dt)
            '14:30:45'
            
            >>> DataFormatters.format_time_br(dt, include_seconds=False)
            '14:30'
        """
        if not dt:
            return ""
        
        try:
            if include_seconds:
                return dt.strftime("%H:%M:%S")
            else:
                return dt.strftime("%H:%M")
        except Exception:
            return str(dt)
    
    
    @staticmethod
    def format_relative_time(dt: datetime) -> str:
        """
        Formata tempo relativo em português.
        
        EXEMPLOS DE SAÍDA:
        - "agora" (< 1 minuto)
        - "há 5 minutos"
        - "há 2 horas"
        - "há 3 dias"
        - "há 2 semanas"
        - "há 1 mês"
        - "há 2 anos"
        
        Args:
            dt: Datetime a ser comparado com agora
            
        Returns:
            String com tempo relativo
            
        Exemplos:
            >>> from datetime import datetime, timedelta
            >>> agora = datetime.utcnow()
            >>> duas_horas_atras = agora - timedelta(hours=2)
            >>> DataFormatters.format_relative_time(duas_horas_atras)
            'há 2 horas'
            
            >>> ontem = agora - timedelta(days=1)
            >>> DataFormatters.format_relative_time(ontem)
            'há 1 dia'
        """
        if not dt:
            return ""
        
        now = datetime.utcnow()
        diff = now - dt
        seconds = diff.total_seconds()
        
        # Menos de 1 minuto
        if seconds < 60:
            return "agora"
        
        # Minutos
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
        
        # Horas
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"há {hours} hora{'s' if hours != 1 else ''}"
        
        # Dias
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"há {days} dia{'s' if days != 1 else ''}"
        
        # Semanas
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"há {weeks} semana{'s' if weeks != 1 else ''}"
        
        # Meses
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"há {months} mês{'es' if months != 1 else ''}"
        
        # Anos
        else:
            years = int(seconds / 31536000)
            return f"há {years} ano{'s' if years != 1 else ''}"
    
    
    @staticmethod
    def format_duration(minutes: int) -> str:
        """
        Formata duração em minutos para texto legível.
        
        FORMATO:
        - "30min" (se < 60 min)
        - "2h" (se múltiplo de 60)
        - "2h 30min" (se tiver horas e minutos)
        
        Args:
            minutes: Duração em minutos
            
        Returns:
            String formatada
            
        Exemplos:
            >>> DataFormatters.format_duration(30)
            '30min'
            
            >>> DataFormatters.format_duration(120)
            '2h'
            
            >>> DataFormatters.format_duration(150)
            '2h 30min'
            
            >>> DataFormatters.format_duration(0)
            'Não especificado'
        """
        if not minutes or minutes <= 0:
            return "Não especificado"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if hours > 0:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}min"
            else:
                return f"{hours}h"
        else:
            return f"{remaining_minutes}min"
    
    
    # ═════════════════════════════════════════════════════════
    # FORMATADORES NUMÉRICOS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_number_br(number: Union[int, float, Decimal], decimals: int = 2) -> str:
        """
        Formata número para padrão brasileiro.
        
        PADRÃO BR:
        - Separador de milhar: . (ponto)
        - Separador decimal: , (vírgula)
        
        Args:
            number: Número a ser formatado
            decimals: Número de casas decimais
            
        Returns:
            String formatada
            
        Exemplos:
            >>> DataFormatters.format_number_br(1234.56)
            '1.234,56'
            
            >>> DataFormatters.format_number_br(1000000, decimals=0)
            '1.000.000'
            
            >>> DataFormatters.format_number_br(3.14159, decimals=3)
            '3,142'
        """
        if number is None:
            return "0"
        
        try:
            # Converte para float
            num = float(number)
            
            # Formata com separador americano primeiro
            formatted = f"{num:,.{decimals}f}"
            
            # Substitui separadores para padrão BR
            # Passo 1: , -> X (temporário)
            formatted = formatted.replace(',', 'X')
            # Passo 2: . -> , (decimal)
            formatted = formatted.replace('.', ',')
            # Passo 3: X -> . (milhar)
            formatted = formatted.replace('X', '.')
            
            return formatted
        except Exception:
            return str(number)
    
    
    @staticmethod
    def format_currency_br(value: Union[int, float, Decimal]) -> str:
        """
        Formata valor monetário brasileiro (Real).
        
        FORMATO: R$ 1.234,56
        
        Args:
            value: Valor em reais
            
        Returns:
            String formatada com R$
            
        Exemplos:
            >>> DataFormatters.format_currency_br(1234.56)
            'R$ 1.234,56'
            
            >>> DataFormatters.format_currency_br(50)
            'R$ 50,00'
            
            >>> DataFormatters.format_currency_br(1000000)
            'R$ 1.000.000,00'
        """
        if value is None:
            value = 0
        
        formatted = DataFormatters.format_number_br(value, decimals=2)
        return f"R$ {formatted}"
    
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Formata porcentagem.
        
        FORMATO: 85,5%
        
        Args:
            value: Valor da porcentagem (85.5 para 85,5%)
            decimals: Casas decimais
            
        Returns:
            String formatada com %
            
        Exemplos:
            >>> DataFormatters.format_percentage(85.5)
            '85,5%'
            
            >>> DataFormatters.format_percentage(100, decimals=0)
            '100%'
            
            >>> DataFormatters.format_percentage(33.333, decimals=2)
            '33,33%'
        """
        if value is None:
            return "0%"
        
        try:
            # Substitui ponto por vírgula
            formatted = f"{value:.{decimals}f}".replace('.', ',')
            return f"{formatted}%"
        except Exception:
            return "0%"
    
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Formata tamanho de arquivo em bytes.
        
        UNIDADES: B, KB, MB, GB, TB
        
        Args:
            size_bytes: Tamanho em bytes
            
        Returns:
            String formatada com unidade
            
        Exemplos:
            >>> DataFormatters.format_file_size(1024)
            '1.0 KB'
            
            >>> DataFormatters.format_file_size(1048576)
            '1.0 MB'
            
            >>> DataFormatters.format_file_size(5242880)
            '5.0 MB'
            
            >>> DataFormatters.format_file_size(0)
            '0 B'
        """
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        # Divide por 1024 até encontrar a unidade adequada
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    
    # ═════════════════════════════════════════════════════════
    # FORMATADORES ESPECÍFICOS DO SISTEMA
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_difficulty_level(level: int) -> Dict[str, Any]:
        """
        Formata nível de dificuldade com detalhes visuais.
        
        RETORNA:
        - name: Nome do nível
        - color: Cor hexadecimal
        - emoji: Emoji representativo
        
        Args:
            level: Nível de 1 a 5
            
        Returns:
            Dicionário com detalhes
            
        Exemplos:
            >>> result = DataFormatters.format_difficulty_level(3)
            >>> result
            {'name': 'Médio', 'color': '#ffc107', 'emoji': '😐'}
            
            >>> result = DataFormatters.format_difficulty_level(5)
            >>> result
            {'name': 'Muito Difícil', 'color': '#dc3545', 'emoji': '😱'}
        """
        difficulty_map = {
            1: {"name": "Muito Fácil", "color": "#28a745", "emoji": "😊"},
            2: {"name": "Fácil", "color": "#6c757d", "emoji": "🙂"},
            3: {"name": "Médio", "color": "#ffc107", "emoji": "😐"},
            4: {"name": "Difícil", "color": "#fd7e14", "emoji": "😰"},
            5: {"name": "Muito Difícil", "color": "#dc3545", "emoji": "😱"}
        }
        
        return difficulty_map.get(level, {
            "name": f"Nível {level}",
            "color": "#6c757d",
            "emoji": "❓"
        })
    
    
    @staticmethod
    def format_school_years(years: List[str]) -> str:
        """
        Formata lista de anos escolares em texto.
        
        FORMATO:
        - 1 ano: "5º ano"
        - 2 anos: "5º e 6º ano"
        - 3+ anos: "5º, 6º e 7º ano"
        
        Args:
            years: Lista de anos escolares
            
        Returns:
            String formatada
            
        Exemplos:
            >>> DataFormatters.format_school_years(["5º ano"])
            '5º ano'
            
            >>> DataFormatters.format_school_years(["5º", "6º"])
            '5º e 6º'
            
            >>> DataFormatters.format_school_years(["5º", "6º", "7º"])
            '5º, 6º e 7º'
        """
        if not years:
            return "Não especificado"
        
        if len(years) == 1:
            return years[0]
        
        if len(years) == 2:
            return f"{years[0]} e {years[1]}"
        
        # 3 ou mais: lista com vírgulas + "e" no final
        return ", ".join(years[:-1]) + f" e {years[-1]}"
    
    
    @staticmethod
    def format_question_preview(statement: str, max_length: int = 100) -> str:
        """
        Formata preview do enunciado da questão.
        
        REGRAS:
        - Remove tags HTML
        - Limita ao tamanho máximo
        - Corta em palavra completa
        - Adiciona "..." se truncado
        
        Args:
            statement: Enunciado completo
            max_length: Tamanho máximo
            
        Returns:
            String truncada
            
        Exemplos:
            >>> text = "Resolva a equação do segundo grau x² - 5x + 6 = 0"
            >>> DataFormatters.format_question_preview(text, max_length=30)
            'Resolva a equação do...'
            
            >>> short_text = "Calcule 2 + 2"
            >>> DataFormatters.format_question_preview(short_text, max_length=30)
            'Calcule 2 + 2'
        """
        if not statement:
            return ""
        
        # Remove tags HTML (se houver)
        clean = re.sub(r'<[^>]+>', '', statement)
        
        # Remove espaços extras
        clean = ' '.join(clean.split())
        
        # Se já está dentro do limite, retorna completo
        if len(clean) <= max_length:
            return clean
        
        # Trunca no último espaço antes do limite
        truncated = clean[:max_length]
        last_space = truncated.rfind(' ')
        
        # Se o último espaço está muito longe, corta direto
        if last_space > max_length * 0.8:
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    
    @staticmethod
    def format_alternatives_list(alternatives: str) -> List[Dict[str, str]]:
        """
        Formata alternativas em lista estruturada.
        
        ENTRADA: "a) Texto A b) Texto B c) Texto C d) Texto D e) Texto E"
        
        SAÍDA: Lista de dicionários com:
        - letter: Letra da alternativa (A, B, C, D, E)
        - content: Conteúdo sem a letra
        - full: Texto completo (A) Conteúdo)
        
        Args:
            alternatives: Texto com todas alternativas
            
        Returns:
            Lista de dicionários
            
        Exemplo:
            >>> text = "a) Opção 1 b) Opção 2 c) Opção 3 d) Opção 4 e) Opção 5"
            >>> result = DataFormatters.format_alternatives_list(text)
            >>> result[0]
            {'letter': 'A', 'content': 'Opção 1', 'full': 'A) Opção 1'}
            
            >>> len(result)
            5
        """
        if not alternatives:
            return []
        
        # Extrai alternativas com regex
        pattern = r'([a-e])\)(.*?)(?=[a-e]\)|$)'
        matches = re.findall(pattern, alternatives, re.IGNORECASE | re.DOTALL)
        
        formatted = []
        for letter, content in matches:
            formatted.append({
                'letter': letter.upper(),
                'content': content.strip(),
                'full': f"{letter.upper()}) {content.strip()}"
            })
        
        return formatted
    
    
    @staticmethod
    def format_user_role(role: str) -> Dict[str, str]:
        """
        Formata role do usuário com detalhes visuais.
        
        RETORNA:
        - name: Nome em português
        - color: Cor para badge
        - icon: Emoji/ícone
        
        Args:
            role: Role do usuário (ADMIN, PROFESSOR, STUDENT)
            
        Returns:
            Dicionário com detalhes
            
        Exemplos:
            >>> result = DataFormatters.format_user_role('PROFESSOR')
            >>> result
            {'name': 'Professor', 'color': '#007bff', 'icon': '👨\u200d🏫'}
            
            >>> result = DataFormatters.format_user_role('ADMIN')
            >>> result
            {'name': 'Administrador', 'color': '#dc3545', 'icon': '👑'}
        """
        role_map = {
            'ADMIN': {
                'name': 'Administrador',
                'color': '#dc3545',
                'icon': '👑'
            },
            'PROFESSOR': {
                'name': 'Professor',
                'color': '#007bff',
                'icon': '👨‍🏫'
            },
            'STUDENT': {
                'name': 'Estudante',
                'color': '#28a745',
                'icon': '👨‍🎓'
            }
        }
        
        return role_map.get(role.upper(), {
            'name': role,
            'color': '#6c757d',
            'icon': '👤'
        })
    
    
    @staticmethod
    def format_exam_status(status: str) -> Dict[str, str]:
        """
        Formata status da prova com detalhes visuais.
        
        RETORNA:
        - name: Nome em português
        - color: Cor para badge
        - icon: Emoji/ícone
        
        Args:
            status: Status da prova (PENDENTE, APLICADA, APROVADA)
            
        Returns:
            Dicionário com detalhes
            
        Exemplos:
            >>> result = DataFormatters.format_exam_status('PENDENTE')
            >>> result
            {'name': 'Pendente', 'color': '#ffc107', 'icon': '⏳'}
            
            >>> result = DataFormatters.format_exam_status('APROVADA')
            >>> result
            {'name': 'Aprovada', 'color': '#28a745', 'icon': '🎉'}
        """
        status_map = {
            'PENDENTE': {
                'name': 'Pendente',
                'color': '#ffc107',
                'icon': '⏳'
            },
            'APLICADA': {
                'name': 'Aplicada',
                'color': '#17a2b8',
                'icon': '✅'
            },
            'APROVADA': {
                'name': 'Aprovada',
                'color': '#28a745',
                'icon': '🎉'
            }
        }
        
        return status_map.get(status.upper(), {
            'name': status,
            'color': '#6c757d',
            'icon': '❓'
        })
    
    
    @staticmethod
    def format_cpf(cpf: str) -> str:
        """
        Formata CPF brasileiro.
        
        FORMATO: 123.456.789-00
        
        Args:
            cpf: CPF sem formatação (apenas números)
            
        Returns:
            CPF formatado
            
        Exemplos:
            >>> DataFormatters.format_cpf("12345678900")
            '123.456.789-00'
            
            >>> DataFormatters.format_cpf("123.456.789-00")
            '123.456.789-00'
        """
        if not cpf:
            return ""
        
        # Remove não numéricos
        cpf_clean = re.sub(r'\D', '', cpf)
        
        # Se não tem 11 dígitos, retorna original
        if len(cpf_clean) != 11:
            return cpf
        
        # Formata: 123.456.789-00
        return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}"
    
    
    @staticmethod
    def format_phone_br(phone: str) -> str:
        """
        Formata telefone brasileiro.
        
        FORMATOS:
        - Celular: (11) 98765-4321
        - Fixo: (11) 3456-7890
        
        Args:
            phone: Telefone sem formatação
            
        Returns:
            Telefone formatado
            
        Exemplos:
            >>> DataFormatters.format_phone_br("11987654321")
            '(11) 98765-4321'
            
            >>> DataFormatters.format_phone_br("1134567890")
            '(11) 3456-7890'
        """
        if not phone:
            return ""
        
        # Remove não numéricos
        phone_clean = re.sub(r'\D', '', phone)
        
        # Celular com 9 dígitos (11 total)
        if len(phone_clean) == 11:
            return f"({phone_clean[:2]}) {phone_clean[2:7]}-{phone_clean[7:]}"
        
        # Fixo com 8 dígitos (10 total)
        elif len(phone_clean) == 10:
            return f"({phone_clean[:2]}) {phone_clean[2:6]}-{phone_clean[6:]}"
        
        # Se não bate, retorna original
        else:
            return phone
    
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """
        Trunca texto mantendo palavras inteiras.
        
        Args:
            text: Texto completo
            max_length: Tamanho máximo
            suffix: Sufixo para texto truncado
            
        Returns:
            Texto truncado ou completo
            
        Exemplos:
            >>> long_text = "Este é um texto muito longo que precisa ser truncado"
            >>> DataFormatters.truncate_text(long_text, max_length=30)
            'Este é um texto muito...'
            
            >>> short_text = "Texto curto"
            >>> DataFormatters.truncate_text(short_text, max_length=30)
            'Texto curto'
        """
        if not text or len(text) <= max_length:
            return text
        
        # Trunca no último espaço antes do limite
        truncated = text[:max_length - len(suffix)]
        last_space = truncated.rfind(' ')
        
        # Se o último espaço está muito perto do início, corta direto
        if last_space > max_length * 0.7:
            truncated = truncated[:last_space]
        
        return truncated + suffix


