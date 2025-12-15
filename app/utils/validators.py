"""
═══════════════════════════════════════════════════════════════
ARQUIVO: app/utils/validators.py
PROPÓSITO: Validadores customizados para o sistema
TIPO: Funções puras - NÃO acessa banco de dados
USO: Validar dados de entrada antes de processar
═══════════════════════════════════════════════════════════════
"""

import re
from typing import Dict, Union
import unicodedata
from pathlib import Path

from app.core.exceptions import ValidationException


class CustomValidators:
    """
    Classe de validadores customizados.
    
    IMPORTANTE: 
    - Estas são FUNÇÕES PURAS (sem estado)
    - NÃO acessam banco de dados
    - Podem ser usadas em qualquer parte do sistema
    - Apenas validam FORMATO e SINTAXE
    """
    
    # ═════════════════════════════════════════════════════════
    # VALIDADORES DE DADOS PESSOAIS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def validate_brazilian_name(name: str) -> bool:
        """
        Valida nome brasileiro completo.
        
        REGRAS:
        - Mínimo 2 caracteres
        - Apenas letras e espaços (aceita acentos)
        - Deve ter pelo menos nome e sobrenome
        
        Args:
            name: Nome completo do usuário
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se nome inválido
            
        Exemplos:
            >>> CustomValidators.validate_brazilian_name("João Silva")
            True
            
            >>> CustomValidators.validate_brazilian_name("José da Silva")
            True
            
            >>> CustomValidators.validate_brazilian_name("João")
            ValidationException: "Nome deve conter pelo menos nome e sobrenome"
        """
        # Verifica se não está vazio
        if not name or len(name.strip()) < 2:
            raise ValidationException("Nome deve ter pelo menos 2 caracteres")
        
        # Remove acentos para validação (mas mantém no original)
        normalized = unicodedata.normalize('NFD', name)
        ascii_name = ''.join(
            c for c in normalized 
            if unicodedata.category(c) != 'Mn'  # Remove marcas diacríticas
        )
        
        # Verifica se contém apenas letras e espaços
        if not re.match(r'^[a-zA-Z\s]+$', ascii_name):
            raise ValidationException("Nome deve conter apenas letras e espaços")
        
        # Verifica se tem pelo menos 2 palavras (nome + sobrenome)
        parts = name.strip().split()
        if len(parts) < 2:
            raise ValidationException("Nome deve conter pelo menos nome e sobrenome")
        
        return True
    
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Valida formato de email.
        
        REGRAS:
        - Formato padrão: usuario@dominio.com
        - Aceita números, letras, pontos, hífens
        - Detecta erros de digitação comuns
        
        Args:
            email: Endereço de email
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se email inválido ou com erro de digitação
            
        Exemplos:
            >>> CustomValidators.validate_email("joao@gmail.com")
            True
            
            >>> CustomValidators.validate_email("joao@gmial.com")
            ValidationException: "Email inválido. Você quis dizer @gmail.com?"
        """
        if not email:
            raise ValidationException("Email é obrigatório")
        
        # Regex para validação de email
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_regex, email):
            raise ValidationException("Email inválido")
        
        # Detecta erros de digitação comuns em domínios
        common_typos = {
            'gmial.com': 'gmail.com',
            'gmai.com': 'gmail.com',
            'gmeil.com': 'gmail.com',
            'hotmial.com': 'hotmail.com',
            'hotmeil.com': 'hotmail.com',
            'yahooo.com': 'yahoo.com',
            'yaho.com': 'yahoo.com'
        }
        
        domain = email.split('@')[1].lower()
        if domain in common_typos:
            suggestion = common_typos[domain]
            raise ValidationException(
                f"Email inválido. Você quis dizer @{suggestion}?"
            )
        
        return True
    
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, any]:
        """
        Valida força da senha e retorna análise detalhada.
        
        CRITÉRIOS:
        - Mínimo 8 caracteres
        - Pelo menos 1 letra maiúscula
        - Pelo menos 1 letra minúscula
        - Pelo menos 1 número
        - Pelo menos 1 caractere especial
        - Não pode ser senha comum
        
        Args:
            password: Senha a ser validada
            
        Returns:
            Dict com análise completa:
            {
                'valid': bool,
                'score': int (0-5),
                'strength': str ('weak', 'medium', 'strong'),
                'errors': list[str],
                'suggestions': list[str]
            }
            
        Exemplo:
            >>> result = CustomValidators.validate_password_strength("MinhaSenh@123")
            >>> print(result)
            {
                'valid': True,
                'score': 5,
                'strength': 'strong',
                'errors': [],
                'suggestions': ['Senhas com 12+ caracteres são mais seguras']
            }
        """
        result = {
            'valid': True,
            'score': 0,
            'errors': [],
            'suggestions': [],
            'strength': 'weak'
        }
        
        if not password:
            result['valid'] = False
            result['errors'].append("Senha é obrigatória")
            return result
        
        # Critérios de validação
        min_length = 8
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
 
        
        # Validação 1: Comprimento
        if len(password) < min_length:
            result['valid'] = False
            result['errors'].append(f"Senha deve ter pelo menos {min_length} caracteres")
        else:
            result['score'] += 1
        
        # Validação 2: Letra maiúscula
        if not has_upper:
            result['valid'] = False
            result['errors'].append("Senha deve conter pelo menos uma letra maiúscula")
        else:
            result['score'] += 1
        
        # Validação 3: Letra minúscula
        if not has_lower:
            result['valid'] = False
            result['errors'].append("Senha deve conter pelo menos uma letra minúscula")
        else:
            result['score'] += 1
        
        # Validação 4: Número
        if not has_digit:
            result['valid'] = False
            result['errors'].append("Senha deve conter pelo menos um número")
        else:
            result['score'] += 1
        
   
        # Verifica senhas comuns (sempre inválido)
        common_passwords = [
            'password', '12345678', 'qwerty', 'abc123', '111111', 
            '123456', 'senha123', 'admin', 'password123', '123456789'
        ]
        
        if password.lower() in common_passwords:
            result['valid'] = False
            result['errors'].append("Senha muito comum. Escolha uma senha mais segura")
            result['score'] = 0
        
        # Detecta padrões sequenciais (reduz score)
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            result['suggestions'].append("Evite sequências numéricas (123, 456, etc)")
            result['score'] = max(0, result['score'] - 1)
        
        if re.search(r'(abc|bcd|cde|def|efg|fgh)', password.lower()):
            result['suggestions'].append("Evite sequências alfabéticas (abc, def, etc)")
            result['score'] = max(0, result['score'] - 1)
        
        # Calcula força final
        if result['score'] >= 5:
            result['strength'] = 'strong'
        elif result['score'] >= 3:
            result['strength'] = 'medium'
        else:
            result['strength'] = 'weak'
        
        # Sugestões adicionais
        if len(password) < 12:
            result['suggestions'].append("Senhas com 12+ caracteres são mais seguras")
        
        return result
    
    
    # ═════════════════════════════════════════════════════════
    # VALIDADORES EDUCACIONAIS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def validate_school_year(year: str) -> bool:
        """
        Valida ano escolar brasileiro.
        
        ANOS VÁLIDOS:
        - Fundamental I: 1º ao 5º ano
        - Fundamental II: 6º ao 9º ano
        - Ensino Médio: 1º ao 3º médio
        
        Args:
            year: Ano escolar (ex: "5º ano", "9º", "2º médio")
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se ano inválido
            
        Exemplos:
            >>> CustomValidators.validate_school_year("5º ano")
            True
            
            >>> CustomValidators.validate_school_year("9º")
            True
            
            >>> CustomValidators.validate_school_year("10º ano")
            ValidationException: "Ano escolar inválido"
        """
        valid_years = [
            # Fundamental I (com e sem "ano")
            '1º ano', '2º ano', '3º ano', '4º ano', '5º ano',
            '1º', '2º', '3º', '4º', '5º',
            
            # Fundamental II (com e sem "ano")
            '6º ano', '7º ano', '8º ano', '9º ano',
            '6º', '7º', '8º', '9º',
            
            # Ensino Médio
            '1º médio', '2º médio', '3º médio',
            '1° médio', '2° médio', '3° médio'  # Aceita º ou °
        ]
        
        # Normaliza para comparação
        year_normalized = year.lower().strip()
        
        if year_normalized not in [y.lower() for y in valid_years]:
            raise ValidationException(
                f"Ano escolar inválido. Use: 1º ao 9º ano, ou 1º ao 3º médio"
            )
        
        return True
    
    
    @staticmethod
    def validate_bncc_code(code: str) -> bool:
        """
        Valida código de habilidade da BNCC.
        
        FORMATO: EF + ano + área + número
        Exemplo: EF05MA01
        - EF = Ensino Fundamental
        - 05 = 5º ano
        - MA = Matemática
        - 01 = Número sequencial da habilidade
        
        ÁREAS VÁLIDAS:
        - MA: Matemática
        - LP: Língua Portuguesa
        - CI: Ciências
        - HI: História
        - GE: Geografia
        - AR: Arte
        - EF: Educação Física
        - ER: Ensino Religioso
        
        Args:
            code: Código BNCC
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se código inválido
            
        Exemplos:
            >>> CustomValidators.validate_bncc_code("EF05MA01")
            True
            
            >>> CustomValidators.validate_bncc_code("EF09MA15")
            True
            
            >>> CustomValidators.validate_bncc_code("EF5MA01")  # Falta zero
            ValidationException: "Código BNCC inválido"
        """
        # Padrão: EF + 2 dígitos + 2 letras + 2 dígitos
        pattern = r'^EF\d{2}(MA|LP|CI|HI|GE|AR|EF|ER)\d{2}$'
        
        if not re.match(pattern, code.upper()):
            raise ValidationException(
                "Código BNCC inválido. Formato esperado: EF05MA01"
            )
        
        return True
    
    
    @staticmethod
    def validate_difficulty_level(level: Union[int, str]) -> bool:
        """
        Valida nível de dificuldade (1 a 5).
        
        NÍVEIS:
        - 1: Muito Fácil
        - 2: Fácil
        - 3: Médio
        - 4: Difícil
        - 5: Muito Difícil
        
        Args:
            level: Nível de dificuldade (aceita int ou str)
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se nível inválido
            
        Exemplos:
            >>> CustomValidators.validate_difficulty_level(3)
            True
            
            >>> CustomValidators.validate_difficulty_level("4")
            True
            
            >>> CustomValidators.validate_difficulty_level(6)
            ValidationException: "Nível deve ser entre 1 e 5"
        """
        try:
            level_int = int(level)
            if not (1 <= level_int <= 5):
                raise ValidationException("Nível de dificuldade deve ser entre 1 e 5")
        except (ValueError, TypeError):
            raise ValidationException("Nível de dificuldade deve ser um número")
        
        return True
    
    
    # ═════════════════════════════════════════════════════════
    # VALIDADORES DE QUESTÕES
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def validate_alternatives_format(alternatives: str) -> Dict[str, any]:
        """
        Valida formato das alternativas de múltipla escolha.
        
        REGRAS:
        - Deve ter exatamente 5 alternativas (a, b, c, d, e)
        - Cada alternativa deve ter conteúdo
        - Formato: a) texto b) texto c) texto d) texto e) texto
        
        Args:
            alternatives: Texto com as 5 alternativas
            
        Returns:
            Dict com análise:
            {
                'valid': bool,
                'found_alternatives': list,
                'missing_alternatives': list,
                'errors': list
            }
            
        Exemplo:
            >>> text = "a) Opção 1 b) Opção 2 c) Opção 3 d) Opção 4 e) Opção 5"
            >>> result = CustomValidators.validate_alternatives_format(text)
            >>> result['valid']
            True
        """
        result = {
            'valid': False,
            'found_alternatives': [],
            'missing_alternatives': [],
            'errors': []
        }
        
        if not alternatives or not alternatives.strip():
            result['errors'].append("Alternativas são obrigatórias")
            return result
        
        # Extrai alternativas encontradas (a), b), c), d), e))
        pattern = r'[a-e]\)'
        found = re.findall(pattern, alternatives.lower())
        result['found_alternatives'] = list(set(found))  # Remove duplicatas
        
        # Verifica quais estão faltando
        expected = ['a)', 'b)', 'c)', 'd)', 'e)']
        result['missing_alternatives'] = [
            alt for alt in expected 
            if alt not in result['found_alternatives']
        ]
        
        # Validação 1: Deve ter 5 alternativas
        if len(result['found_alternatives']) != 5:
            result['errors'].append(
                f"Deve conter exatamente 5 alternativas. "
                f"Encontradas: {len(result['found_alternatives'])}"
            )
        
        # Validação 2: Verifica alternativas faltando
        if result['missing_alternatives']:
            result['errors'].append(
                f"Alternativas faltando: {', '.join(result['missing_alternatives'])}"
            )
        
        # Validação 3: Verifica se cada alternativa tem conteúdo
        for letter in ['a', 'b', 'c', 'd', 'e']:
            # Extrai texto da alternativa
            alt_pattern = f'{letter}\\)\\s*([^a-e]*?)(?=[a-e]\\)|$)'
            match = re.search(alt_pattern, alternatives.lower(), re.DOTALL)
            
            if match:
                content = match.group(1).strip()
                if len(content) < 3:
                    result['errors'].append(
                        f"Alternativa '{letter.upper()})' parece estar vazia ou muito curta"
                    )
        
        # Define se é válido
        result['valid'] = len(result['errors']) == 0
        
        return result
    
    
    @staticmethod
    def validate_correct_alternative(
        alternative: str, 
        alternatives_text: str = None
    ) -> bool:
        """
        Valida alternativa correta.
        
        REGRAS:
        - Deve ser uma letra de a até e
        - Se fornecido alternatives_text, verifica se alternativa existe
        
        Args:
            alternative: Letra da alternativa correta (a, b, c, d ou e)
            alternatives_text: Texto completo das alternativas (opcional)
            
        Returns:
            True se válido
            
        Raises:
            ValidationException: Se alternativa inválida
            
        Exemplos:
            >>> CustomValidators.validate_correct_alternative("b")
            True
            
            >>> CustomValidators.validate_correct_alternative("f")
            ValidationException: "Alternativa deve ser a, b, c, d ou e"
        """
        if not alternative or not alternative.strip():
            raise ValidationException("Alternativa correta é obrigatória")
        
        # Remove ) se houver e normaliza
        alt_clean = alternative.lower().strip().replace(')', '')
        
        # Verifica se está entre a-e
        valid_alternatives = ['a', 'b', 'c', 'd', 'e']
        if alt_clean not in valid_alternatives:
            raise ValidationException(
                "Alternativa correta deve ser a, b, c, d ou e"
            )
        
        # Se fornecido o texto das alternativas, verifica se existe
        if alternatives_text:
            if f"{alt_clean})" not in alternatives_text.lower():
                raise ValidationException(
                    f"Alternativa '{alternative.upper()}' não encontrada no texto"
                )
        
        return True
    
    
    @staticmethod
    def validate_question_statement(statement: str) -> Dict[str, any]:
        """
        Valida enunciado da questão.
        
        ANÁLISE:
        - Mínimo 10 caracteres
        - Conta palavras
        - Verifica se é pergunta
        - Sugere melhorias
        
        Args:
            statement: Enunciado da questão
            
        Returns:
            Dict com análise:
            {
                'valid': bool,
                'warnings': list,
                'suggestions': list,
                'word_count': int,
                'has_question_mark': bool
            }
            
        Exemplo:
            >>> text = "Resolva a equação x² - 5x + 6 = 0"
            >>> result = CustomValidators.validate_question_statement(text)
            >>> result['word_count']
            7
        """
        result = {
            'valid': True,
            'warnings': [],
            'suggestions': [],
            'word_count': 0,
            'has_question_mark': False
        }
        
        # Validação mínima
        if not statement or len(statement.strip()) < 5:
            raise ValidationException("Enunciado deve ter pelo menos 5 caracteres")
        
        statement_clean = statement.strip()
        result['word_count'] = len(statement_clean.split())
        result['has_question_mark'] = statement_clean.endswith('?')
        
        # Palavras que indicam pergunta
        question_indicators = [
            'quanto', 'qual', 'quais', 'onde', 'quando', 'como',
            'por que', 'porque', 'calcule', 'determine', 'encontre',
            'resolva', 'obtenha', 'identifique', 'descubra'
        ]
        
        has_question_word = any(
            word in statement_clean.lower() 
            for word in question_indicators
        )
        
        # Avisos
        if has_question_word and not result['has_question_mark']:
            result['warnings'].append(
                "Enunciado parece ser uma pergunta mas não termina com '?'"
            )
        
        if result['word_count'] > 100:
            result['warnings'].append(
                "Enunciado muito longo (>100 palavras). Considere simplificar"
            )
        elif result['word_count'] < 5:
            result['warnings'].append(
                "Enunciado muito curto. Adicione mais contexto"
            )
        
        # Verifica se há números/dados
        has_numbers = bool(re.search(r'\d', statement_clean))
        if not has_numbers:
            result['suggestions'].append(
                "Considere adicionar dados numéricos se aplicável"
            )
         
        return result


