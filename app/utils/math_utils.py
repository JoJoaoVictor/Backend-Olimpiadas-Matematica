"""
═══════════════════════════════════════════════════════════════
ARQUIVO: app/utils/math_utils.py
PROPÓSITO: Utilitários matemáticos para questões e cálculos
TIPO: Funções puras - NÃO acessa banco de dados
USO: Validar, resolver e processar expressões matemáticas
═══════════════════════════════════════════════════════════════
"""

import numpy as np
import sympy as sp
from sympy import symbols, solve, diff, integrate, simplify, latex
from typing import Any, Dict, List, Optional, Tuple, Union
import re
import math
import random

from app.core.exceptions import ValidationException

 
class MathUtils:
    """
    Classe de utilitários matemáticos.
    
    IMPORTANTE:
    - Usa SymPy para álgebra simbólica
    - Usa NumPy para computação numérica
    - Funções puras (sem estado)
    - Validação e processamento matemático
    """
    
    # ═════════════════════════════════════════════════════════
    # VALIDAÇÃO DE EXPRESSÕES MATEMÁTICAS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def validate_mathematical_expression(expression: str) -> Dict[str, Any]:
        """
        Valida expressão matemática e analisa suas características.
        
        ANÁLISE RETORNADA:
        - valid: Se é válida
        - variables: Variáveis encontradas (x, y, etc)
        - complexity: 'baixa', 'média', 'alta'
        - type: Tipo da expressão (linear, quadratic, etc)
        - error: Mensagem de erro se inválida
        
        Args:
            expression: Expressão matemática como string
            
        Returns:
            Dicionário com análise completa
            
        Exemplos:
            >>> result = MathUtils.validate_mathematical_expression("x**2 + 2*x + 1")
            >>> result['valid']
            True
            >>> result['type']
            'quadratic'
            >>> result['variables']
            ['x']
            
            >>> result = MathUtils.validate_mathematical_expression("2*x + 3")
            >>> result['type']
            'linear'
        """
        result = {
            'valid': False,
            'error': None,
            'variables': [],
            'complexity': 'baixa',
            'type': 'unknown',
            'parsed': None,
            'latex': None
        }
        
        try:
            # Limpa a expressão
            clean_expr = MathUtils._clean_expression(expression)
            
            # Tenta parsear com SymPy
            parsed = sp.sympify(clean_expr)
            
            # Extrai variáveis
            result['variables'] = [str(var) for var in parsed.free_symbols]
            
            # Determina tipo da expressão
            result['type'] = MathUtils._determine_expression_type(parsed)
            
            # Calcula complexidade
            result['complexity'] = MathUtils._calculate_complexity(parsed)
            
            # Sucesso
            result['valid'] = True
            result['parsed'] = str(parsed)
            result['latex'] = latex(parsed)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    @staticmethod
    def _clean_expression(expression: str) -> str:
        """
        Limpa expressão matemática para parsing.
        
        SUBSTITUI:
        - × → *
        - ÷ → /
        - ² → **2
        - √ → sqrt
        - π → pi
        
        Args:
            expression: Expressão original
            
        Returns:
            Expressão limpa
            
        Exemplo:
            >>> MathUtils._clean_expression("x² + 2×x")
            'x**2 + 2*x'
        """
        clean = expression.strip()
        
        # Substitui símbolos matemáticos comuns
        replacements = {
            '×': '*',
            '÷': '/',
            '²': '**2',
            '³': '**3',
            '√': 'sqrt',
            'π': 'pi',
            '∞': 'oo'
        }
        
        for old, new in replacements.items():
            clean = clean.replace(old, new)
        
        return clean
    
    
    @staticmethod
    def _determine_expression_type(expr) -> str:
        """
        Determina tipo da expressão matemática.
        
        TIPOS:
        - linear: x + 2
        - quadratic: x² + 2x + 1
        - polynomial_degree_n: x³, x⁴, etc
        - trigonometric: sin(x), cos(x)
        - exponential_logarithmic: e^x, log(x)
        - radical: √x
        - algebraic: genérica
        
        Args:
            expr: Expressão SymPy
            
        Returns:
            String com tipo
        """
        # Verifica se é polinômio
        if expr.is_polynomial():
            degree = sp.degree(expr)
            if degree == 1:
                return 'linear'
            elif degree == 2:
                return 'quadratic'
            elif degree == 3:
                return 'cubic'
            else:
                return f'polynomial_degree_{degree}'
        
        # Verifica funções trigonométricas
        if expr.has(sp.sin, sp.cos, sp.tan):
            return 'trigonometric'
        
        # Verifica exponencial/logaritmo
        if expr.has(sp.exp, sp.log, sp.ln):
            return 'exponential_logarithmic'
        
        # Verifica radicais
        if expr.has(sp.sqrt):
            return 'radical'
        
        return 'algebraic'
    
    
    @staticmethod
    def _calculate_complexity(expr) -> str:
        """
        Calcula complexidade da expressão.
        
        SCORE:
        - Cada operação: +1
        - Cada função: +1
        
        NÍVEIS:
        - < 3 operações: 'baixa'
        - 3-6 operações: 'média'
        - > 6 operações: 'alta'
        
        Args:
            expr: Expressão SymPy
            
        Returns:
            'baixa', 'média' ou 'alta'
        """
        operations = 0
        
        # Conta operações
        operations += len(expr.atoms(sp.Add))      # +, -
        operations += len(expr.atoms(sp.Mul))      # *, /
        operations += len(expr.atoms(sp.Pow))      # ^
        operations += len(expr.atoms(sp.Function)) # sin, cos, etc
        
        if operations < 3:
            return 'baixa'
        elif operations < 6:
            return 'média'
        else:
            return 'alta'
    
    
    # ═════════════════════════════════════════════════════════
    # RESOLUÇÃO DE EQUAÇÕES
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def solve_equation(equation: str, variable: str = 'x') -> Dict[str, Any]:
        """
        Resolve equação matemática.
        
        SUPORTA:
        - Equações lineares: 2x + 3 = 0
        - Equações quadráticas: x² - 5x + 6 = 0
        - Equações de grau superior
        - Sistemas simples
        
        Args:
            equation: Equação como string (pode ter ou não "=")
            variable: Variável a resolver (padrão: 'x')
            
        Returns:
            Dicionário com:
            - solved: bool
            - solutions: lista de soluções
            - solutions_latex: soluções em LaTeX
            - steps: passos da solução
            - error: mensagem de erro se falhar
            
        Exemplos:
            >>> result = MathUtils.solve_equation("x**2 - 5*x + 6 = 0", "x")
            >>> result['solutions']
            ['2', '3']
            
            >>> result = MathUtils.solve_equation("2*x + 4 = 0", "x")
            >>> result['solutions']
            ['-2']
        """
        result = {
            'solved': False,
            'solutions': [],
            'solutions_latex': [],
            'steps': [],
            'error': None
        }
        
        try:
            # Limpa equação
            clean_eq = MathUtils._clean_expression(equation)
            
            # Define variável
            var = symbols(variable)
            
            # Parseia equação
            if '=' in clean_eq:
                left, right = clean_eq.split('=')
                equation_obj = sp.Eq(sp.sympify(left), sp.sympify(right))
                result['steps'].append(f"Equação: {left} = {right}")
            else:
                equation_obj = sp.sympify(clean_eq)
                result['steps'].append(f"Equação: {clean_eq} = 0")
            
            # Resolve
            solutions = solve(equation_obj, var)
            
            # Formata soluções
            result['solutions'] = [str(sol) for sol in solutions]
            result['solutions_latex'] = [latex(sol) for sol in solutions]
            result['solved'] = True
            
            # Gera passos
            if len(solutions) == 0:
                result['steps'].append("Nenhuma solução real encontrada")
            elif len(solutions) == 1:
                result['steps'].append(f"Solução: {variable} = {solutions[0]}")
            else:
                result['steps'].append(f"Soluções encontradas:")
                for i, sol in enumerate(solutions, 1):
                    result['steps'].append(f"  {variable}_{i} = {sol}")
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    @staticmethod
    def check_equation_solution(
        equation: str, 
        variable: str, 
        solution: float, 
        tolerance: float = 1e-6
    ) -> bool:
        """
        Verifica se um valor é solução da equação.
        
        Args:
            equation: Equação como string
            variable: Variável
            solution: Valor a verificar
            tolerance: Tolerância numérica
            
        Returns:
            True se é solução
            
        Exemplo:
            >>> MathUtils.check_equation_solution("x**2 - 5*x + 6 = 0", "x", 2)
            True
            
            >>> MathUtils.check_equation_solution("x**2 - 5*x + 6 = 0", "x", 5)
            False
        """
        try:
            clean_eq = MathUtils._clean_expression(equation)
            var = symbols(variable)
            
            # Parseia lados da equação
            if '=' in clean_eq:
                left, right = clean_eq.split('=')
                left_expr = sp.sympify(left)
                right_expr = sp.sympify(right)
            else:
                left_expr = sp.sympify(clean_eq)
                right_expr = 0
            
            # Substitui valor
            left_val = float(left_expr.subs(var, solution).evalf())
            right_val = float(right_expr.subs(var, solution).evalf())
            
            # Verifica se são iguais (com tolerância)
            return abs(left_val - right_val) < tolerance
            
        except Exception:
            return False
    
    
    # ═════════════════════════════════════════════════════════
    # CÁLCULO DIFERENCIAL E INTEGRAL
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_derivative(expression: str, variable: str = 'x') -> Dict[str, Any]:
        """
        Calcula derivada de uma expressão.
        
        Args:
            expression: Expressão matemática
            variable: Variável em relação à qual derivar
            
        Returns:
            Dicionário com:
            - calculated: bool
            - derivative: derivada como string
            - derivative_latex: derivada em LaTeX
            - error: mensagem de erro se falhar
            
        Exemplos:
            >>> result = MathUtils.calculate_derivative("x**2 + 2*x", "x")
            >>> result['derivative']
            '2*x + 2'
            
            >>> result = MathUtils.calculate_derivative("sin(x)", "x")
            >>> result['derivative']
            'cos(x)'
        """
        result = {
            'calculated': False,
            'derivative': None,
            'derivative_latex': None,
            'simplified': None,
            'error': None
        }
        
        try:
            clean_expr = MathUtils._clean_expression(expression)
            var = symbols(variable)
            expr = sp.sympify(clean_expr)
            
            # Calcula derivada
            derivative = diff(expr, var)
            
            # Simplifica
            simplified = simplify(derivative)
            
            result['derivative'] = str(derivative)
            result['derivative_latex'] = latex(derivative)
            result['simplified'] = str(simplified)
            result['calculated'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    @staticmethod
    def calculate_integral(expression: str, variable: str = 'x') -> Dict[str, Any]:
        """
        Calcula integral indefinida de uma expressão.
        
        Args:
            expression: Expressão matemática
            variable: Variável de integração
            
        Returns:
            Dicionário com:
            - calculated: bool
            - integral: integral como string (+ C implícito)
            - integral_latex: integral em LaTeX
            - error: mensagem de erro se falhar
            
        Exemplos:
            >>> result = MathUtils.calculate_integral("2*x + 1", "x")
            >>> result['integral']
            'x**2 + x'
            
            >>> result = MathUtils.calculate_integral("sin(x)", "x")
            >>> result['integral']
            '-cos(x)'
        """
        result = {
            'calculated': False,
            'integral': None,
            'integral_latex': None,
            'error': None
        }
        
        try:
            clean_expr = MathUtils._clean_expression(expression)
            var = symbols(variable)
            expr = sp.sympify(clean_expr)
            
            # Calcula integral
            integral_result = integrate(expr, var)
            
            result['integral'] = str(integral_result)
            result['integral_latex'] = latex(integral_result)
            result['calculated'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    # ═════════════════════════════════════════════════════════
    # AVALIAÇÃO E SIMPLIFICAÇÃO
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def evaluate_at_point(
        expression: str, 
        variable: str, 
        value: float
    ) -> Dict[str, Any]:
        """
        Avalia expressão em um ponto específico.
        
        Args:
            expression: Expressão matemática
            variable: Variável
            value: Valor para substituir
            
        Returns:
            Dicionário com:
            - evaluated: bool
            - value: resultado numérico
            - error: mensagem de erro se falhar
            
        Exemplos:
            >>> result = MathUtils.evaluate_at_point("x**2 + 2*x", "x", 3)
            >>> result['value']
            15.0
            
            >>> result = MathUtils.evaluate_at_point("sin(x)", "x", 3.14159/2)
            >>> result['value']
            1.0
        """
        result = {
            'evaluated': False,
            'value': None,
            'error': None
        }
        
        try:
            clean_expr = MathUtils._clean_expression(expression)
            var = symbols(variable)
            expr = sp.sympify(clean_expr)
            
            # Substitui e avalia
            evaluated = expr.subs(var, value)
            result['value'] = float(evaluated.evalf())
            result['evaluated'] = True
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    @staticmethod
    def simplify_expression(expression: str) -> Dict[str, Any]:
        """
        Simplifica expressão matemática.
        
        Args:
            expression: Expressão a simplificar
            
        Returns:
            Dicionário com:
            - simplified: expressão simplificada
            - simplified_latex: em LaTeX
            - original: expressão original
            
        Exemplos:
            >>> result = MathUtils.simplify_expression("x**2 - 2*x*y + y**2")
            >>> result['simplified']
            '(x - y)**2'
            
            >>> result = MathUtils.simplify_expression("(x + 2)*(x - 2)")
            >>> result['simplified']
            'x**2 - 4'
        """
        result = {
            'original': expression,
            'simplified': None,
            'simplified_latex': None,
            'error': None
        }
        
        try:
            clean_expr = MathUtils._clean_expression(expression)
            expr = sp.sympify(clean_expr)
            
            # Simplifica
            simplified = simplify(expr)
            
            result['simplified'] = str(simplified)
            result['simplified_latex'] = latex(simplified)
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    
    # ═════════════════════════════════════════════════════════
    # SEQUÊNCIAS MATEMÁTICAS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def generate_sequence(pattern: str, length: int = 10) -> List[Union[int, float]]:
        """
        Gera sequência matemática baseada em padrão.
        
        PADRÕES DISPONÍVEIS:
        - fibonacci: 0, 1, 1, 2, 3, 5, 8, 13...
        - prime: 2, 3, 5, 7, 11, 13...
        - square: 1, 4, 9, 16, 25...
        - cube: 1, 8, 27, 64...
        - even: 2, 4, 6, 8...
        - odd: 1, 3, 5, 7...
        
        Args:
            pattern: Tipo de sequência
            length: Quantidade de termos
            
        Returns:
            Lista com números da sequência
            
        Exemplos:
            >>> MathUtils.generate_sequence('fibonacci', 8)
            [0, 1, 1, 2, 3, 5, 8, 13]
            
            >>> MathUtils.generate_sequence('prime', 5)
            [2, 3, 5, 7, 11]
            
            >>> MathUtils.generate_sequence('square', 5)
            [1, 4, 9, 16, 25]
        """
        sequences = {
            'fibonacci': MathUtils._fibonacci_sequence,
            'prime': MathUtils._prime_sequence,
            'square': lambda n: [i**2 for i in range(1, n+1)],
            'cube': lambda n: [i**3 for i in range(1, n+1)],
            'even': lambda n: [2*i for i in range(1, n+1)],
            'odd': lambda n: [2*i-1 for i in range(1, n+1)]
        }
        
        if pattern.lower() in sequences:
            return sequences[pattern.lower()](length)
        
        return []
    
    
    @staticmethod
    def _fibonacci_sequence(n: int) -> List[int]:
        """Gera sequência de Fibonacci."""
        if n <= 0:
            return []
        elif n == 1:
            return [0]
        elif n == 2:
            return [0, 1]
        
        fib = [0, 1]
        for i in range(2, n):
            fib.append(fib[i-1] + fib[i-2])
        
        return fib
    
    
    @staticmethod
    def _prime_sequence(n: int) -> List[int]:
        """Gera sequência de números primos."""
        if n <= 0:
            return []
        
        primes = []
        candidate = 2
        
        while len(primes) < n:
            is_prime = True
            
            # Verifica se é divisível por algum primo anterior
            for p in primes:
                if p * p > candidate:
                    break
                if candidate % p == 0:
                    is_prime = False
                    break
            
            if is_prime:
                primes.append(candidate)
            
            candidate += 1
        
        return primes
    
    
    # ═════════════════════════════════════════════════════════
    # ESTATÍSTICAS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_statistics(data: List[float]) -> Dict[str, float]:
        """
        Calcula estatísticas básicas de um conjunto de dados.
        
        CALCULA:
        - Média (mean)
        - Mediana (median)
        - Moda (mode)
        - Desvio padrão (std_dev)
        - Variância (variance)
        - Mínimo (min)
        - Máximo (max)
        - Amplitude (range)
        - Contagem (count)
        
        Args:
            data: Lista de números
            
        Returns:
            Dicionário com estatísticas
            
        Exemplo:
            >>> data = [1, 2, 2, 3, 4, 5, 5, 5, 6, 7]
            >>> stats = MathUtils.calculate_statistics(data)
            >>> stats['mean']
            4.0
            >>> stats['mode']
            5.0
        """
        if not data:
            return {}
        
        try:
            # Calcula moda (valor mais frequente)
            from collections import Counter
            counter = Counter(data)
            mode_value = counter.most_common(1)[0][0] if counter else None
            
            return {
                'mean': float(np.mean(data)),
                'median': float(np.median(data)),
                'mode': float(mode_value) if mode_value is not None else None,
                'std_dev': float(np.std(data)),
                'variance': float(np.var(data)),
                'min': float(min(data)),
                'max': float(max(data)),
                'range': float(max(data) - min(data)),
                'count': len(data)
            }
        except Exception:
            return {}
    
    
    # ═════════════════════════════════════════════════════════
    # FORMATAÇÃO
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def format_mathematical_expression(
        expr: str, 
        format_type: str = 'latex'
    ) -> str:
        """
        Formata expressão matemática para diferentes formatos.
        
        FORMATOS:
        - latex: \\frac{x^2}{2}
        - unicode: x²/2 (com símbolos especiais)
        - ascii: x^2/2 (apenas ASCII)
        
        Args:
            expr: Expressão matemática
            format_type: Tipo de formatação
            
        Returns:
            Expressão formatada
            
        Exemplos:
            >>> MathUtils.format_mathematical_expression("x**2/2", "latex")
            '\\\\frac{x^{2}}{2}'
            
            >>> MathUtils.format_mathematical_expression("x**2", "unicode")
            'x²'
        """
        try:
            parsed = sp.sympify(expr)
            
            if format_type == 'latex':
                return latex(parsed)
            elif format_type == 'unicode':
                return sp.pretty(parsed, use_unicode=True)
            elif format_type == 'ascii':
                return sp.pretty(parsed, use_unicode=False)
            else:
                return str(parsed)
                
        except Exception:
            return expr

