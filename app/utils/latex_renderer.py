"""Utilitários para renderização LaTeX."""

import re
import sympy as sp
from sympy.parsing.latex import parse_latex
from sympy import latex, sympify
from typing import Optional, Dict, Any
import logging

from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class LaTeXRenderer:
    """Renderizador LaTeX avançado."""
    
    # Comandos LaTeX permitidos (whitelist)
    ALLOWED_COMMANDS = {
        'frac', 'sqrt', 'sum', 'prod', 'int', 'lim',
        'sin', 'cos', 'tan', 'log', 'ln', 'exp',
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'theta',
        'pi', 'infty', 'partial', 'nabla',
        'cdot', 'times', 'div', 'pm', 'mp',
        'leq', 'geq', 'neq', 'approx', 'equiv',
        'left', 'right', 'begin', 'end', 'array', 'matrix',
        'text', 'textbf', 'textit', 'mathbf', 'mathit',
        'overline', 'underline', 'vec', 'hat', 'tilde',
        'quad', 'qquad', 'vspace', 'hspace'
    }
    
    # Ambientes LaTeX permitidos
    ALLOWED_ENVIRONMENTS = {
        'equation', 'align', 'array', 'matrix', 'pmatrix', 'bmatrix'
    }
    
    @staticmethod
    def validate_latex_syntax(latex_code: str) -> Dict[str, Any]:
        """Valida sintaxe LaTeX e retorna informações."""
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'commands_used': [],
            'complexity_score': 0
        }
        
        try:
            # Remove espaços extras
            latex_code = latex_code.strip()
            
            if not latex_code:
                result['errors'].append("Código LaTeX vazio")
                return result
            
            # Verifica comandos não permitidos
            forbidden_cmds = LaTeXRenderer._check_forbidden_commands(latex_code)
            if forbidden_cmds:
                result['errors'].extend([f"Comando não permitido: {cmd}" for cmd in forbidden_cmds])
                return result
            
            # Extrai comandos usados
            result['commands_used'] = LaTeXRenderer._extract_commands(latex_code)
            
            # Verifica balanceamento de chaves
            if not LaTeXRenderer._check_brace_balance(latex_code):
                result['errors'].append("Chaves não balanceadas")
                return result
            
            # Calcula complexidade
            result['complexity_score'] = LaTeXRenderer._calculate_complexity(latex_code)
            
            # Tenta parsear com SymPy (se possível)
            try:
                # Remove ambientes LaTeX para teste de parsing
                clean_code = LaTeXRenderer._clean_for_parsing(latex_code)
                if clean_code:
                    parsed = parse_latex(clean_code)
                    result['sympy_compatible'] = True
                    result['parsed_expression'] = str(parsed)
                else:
                    result['sympy_compatible'] = False
            except Exception as e:
                result['sympy_compatible'] = False
                result['warnings'].append(f"Não compatível com SymPy: {str(e)}")
            
            result['valid'] = True
            
        except Exception as e:
            result['errors'].append(f"Erro na validação: {str(e)}")
        
        return result
    
    @staticmethod
    def convert_to_mathml(latex_code: str) -> Optional[str]:
        """Converte LaTeX para MathML."""
        try:
            # Remove ambientes LaTeX
            clean_code = LaTeXRenderer._clean_for_parsing(latex_code)
            
            if not clean_code:
                return None
            
            # Converte usando SymPy
            expr = parse_latex(clean_code)
            
            # SymPy não tem MathML direto, mas podemos usar outras bibliotecas
            # Por enquanto, retorna None (implementar com latex2mathml se necessário)
            return None
            
        except Exception as e:
            logger.error(f"Erro na conversão MathML: {e}")
            return None
    
    @staticmethod
    def simplify_expression(latex_code: str) -> Optional[str]:
        """Simplifica expressão matemática."""
        try:
            clean_code = LaTeXRenderer._clean_for_parsing(latex_code)
            if not clean_code:
                return None
            
            # Parse e simplifica
            expr = parse_latex(clean_code)
            simplified = sp.simplify(expr)
            
            # Converte de volta para LaTeX
            return latex(simplified)
            
        except Exception as e:
            logger.error(f"Erro na simplificação: {e}")
            return None
    
    @staticmethod
    def _check_forbidden_commands(latex_code: str) -> list:
        """Verifica comandos proibidos."""
        forbidden = [
            '\\input', '\\include', '\\write', '\\open', '\\read',
            '\\immediate', '\\shell', '\\system', '\\execute',
            '\\def', '\\let', '\\expandafter', '\\catcode',
            '\\newcommand', '\\renewcommand', '\\providecommand'
        ]
         
        found = []
        for cmd in forbidden:
            if cmd in latex_code:
                found.append(cmd)
        
        return found
    
    @staticmethod
    def _extract_commands(latex_code: str) -> list:
        """Extrai comandos LaTeX usados."""
        # Regex para comandos LaTeX: \comando
        pattern = r'\\([a-zA-Z]+)'
        commands = re.findall(pattern, latex_code)
        return list(set(commands))  # Remove duplicatas
    
    @staticmethod
    def _check_brace_balance(latex_code: str) -> bool:
        """Verifica se chaves estão balanceadas."""
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        
        i = 0
        while i < len(latex_code):
            char = latex_code[i]
            
            # Ignora caracteres escapados
            if char == '\\' and i + 1 < len(latex_code):
                i += 2
                continue
            
            if char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack:
                    return False
                last = stack.pop()
                if pairs[last] != char:
                    return False
            
            i += 1
        
        return len(stack) == 0
    
    @staticmethod
    def _calculate_complexity(latex_code: str) -> int:
        """Calcula score de complexidade."""
        score = 0
        
        # Comandos básicos = 1 ponto cada
        basic_commands = ['frac', 'sqrt', 'sum', 'prod', 'int']
        for cmd in basic_commands:
            score += latex_code.count(f'\\{cmd}') * 1
        
        # Funções trigonométricas = 1 ponto
        trig_functions = ['sin', 'cos', 'tan', 'sec', 'csc', 'cot']
        for func in trig_functions:
            score += latex_code.count(f'\\{func}') * 1
        
        # Símbolos gregos = 1 ponto
        greek_letters = ['alpha', 'beta', 'gamma', 'delta', 'theta', 'lambda', 'mu', 'pi']
        for letter in greek_letters:
            score += latex_code.count(f'\\{letter}') * 1
        
        # Ambientes = 3 pontos
        environments = ['matrix', 'array', 'align', 'equation']
        for env in environments:
            score += latex_code.count(f'\\begin{{{env}}}') * 3
        
        # Subscritos e sobrescritos
        score += latex_code.count('_') + latex_code.count('^')
        
        return score
    
    @staticmethod
    def _clean_for_parsing(latex_code: str) -> str:
        """Limpa código LaTeX para parsing com SymPy."""
        # Remove ambientes LaTeX que SymPy não entende
        environments_to_remove = ['equation', 'align', 'array']
        
        cleaned = latex_code
        
        for env in environments_to_remove:
            # Remove \begin{env} e \end{env}
            pattern = f 
            r'\\begin{{{env}}}(.*?)\\end{{{env}}}'
            matches = re.findall(pattern, cleaned, re.DOTALL)
            for match in matches:
                cleaned = cleaned.replace(
                    f'\\begin{{{env}}}{match}\\end{{{env}}}', 
                    match.strip()
                )
        
        # Remove comandos de formatação
        formatting_commands = ['text', 'textbf', 'textit', 'mathbf', 'mathit']
        for cmd in formatting_commands:
            pattern = f 
            r'\\{cmd}{{(.*?)}}'
            cleaned = re.sub(pattern, r'\1', cleaned)
        
        # Remove espaçamentos
        spacing_commands = ['quad', 'qquad', 'hspace', 'vspace']
        for cmd in spacing_commands:
            pattern = f 
            r'\\{cmd}{{.*?}}'
            cleaned = re.sub(pattern, '', cleaned)
        
        return cleaned.strip()
