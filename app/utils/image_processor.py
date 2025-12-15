"""
═══════════════════════════════════════════════════════════════
ARQUIVO: app/utils/image_processor.py
PROPÓSITO: Processamento avançado de imagens para questões
TIPO: Funções puras - NÃO acessa banco de dados
USO: Otimizar, processar e analisar imagens matemáticas
DEPENDÊNCIAS: OpenCV (cv2), Pillow (PIL), NumPy
═══════════════════════════════════════════════════════════════
"""

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from typing import Tuple, Optional, Dict, Any, List
import io
from pathlib import Path
import base64

from app.core.exceptions import ValidationException


class ImageProcessor:
    """
    Classe de processamento de imagens.
    
    FUNCIONALIDADES:
    - Otimização de imagens matemáticas
    - Criação de thumbnails
    - Detecção de texto/símbolos
    - Conversões de formato
    - Marca d'água
    
    IMPORTANTE:
    - Funções puras (sem estado)
    - NÃO salva no banco de dados
    - Apenas processa arquivos
    """
    
    # Configurações padrão
    MAX_DIMENSION = 2048
    THUMBNAIL_SIZE = (300, 300)
    QUALITY_STANDARD = 85
    QUALITY_THUMBNAIL = 80
    
    
    # ═════════════════════════════════════════════════════════
    # OTIMIZAÇÃO DE IMAGENS MATEMÁTICAS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def optimize_math_image(
        image_path: str, 
        output_path: str = None
    ) -> Dict[str, Any]:
        """
        Otimiza imagem matemática para melhor legibilidade.
        
        PROCESSOS:
        1. Converte para escala de cinza
        2. Remove ruído (bilateral filter)
        3. Melhora contraste (CLAHE)
        4. Binarização adaptativa (texto fica mais nítido)
        5. Morfologia para limpeza
        
        USO: Imagens de questões, fórmulas manuscritas, diagramas
        
        Args:
            image_path: Caminho da imagem original
            output_path: Caminho para salvar (None = sobrescreve)
            
        Returns:
            Dict com estatísticas:
            - original_size: dimensões originais
            - processed_size: dimensões processadas
            - noise_reduction: bool
            - contrast_enhanced: bool
            - text_optimized: bool
            - output_path: onde foi salva
            - file_size_reduction: % de redução
            
        Exemplo:
            >>> stats = ImageProcessor.optimize_math_image("questao.jpg")
            >>> stats['noise_reduction']
            True
            >>> stats['file_size_reduction']
            45.2
        """
        try:
            # Carrega imagem com OpenCV
            img = cv2.imread(image_path)
            if img is None:
                raise ValidationException("Não foi possível carregar a imagem")
            
            original_shape = img.shape
            
            # Passo 1: Converte para escala de cinza
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Passo 2: Remove ruído preservando bordas
            # bilateralFilter: remove ruído mas mantém bordas nítidas
            denoised = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Passo 3: Melhora contraste adaptativo (CLAHE)
            # CLAHE = Contrast Limited Adaptive Histogram Equalization
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
            
            # Passo 4: Binarização adaptativa para texto
            # Fundo branco, texto preto
            binary = cv2.adaptiveThreshold(
                enhanced, 
                255,                              # Valor máximo
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,   # Método adaptativo
                cv2.THRESH_BINARY,                # Tipo
                11,                               # Tamanho do bloco
                2                                 # Constante subtraída
            )
            
            # Passo 5: Morfologia para limpar pequenos artefatos
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # Passo 6: Remove ruído muito pequeno
            cleaned = cv2.medianBlur(cleaned, 3)
            
            # Define caminho de saída
            if output_path is None:
                output_path = image_path.replace('.', '_optimized.')
            
            # Salva imagem processada
            cv2.imwrite(output_path, cleaned)
            
            # Calcula estatísticas
            original_size = Path(image_path).stat().st_size
            processed_size = Path(output_path).stat().st_size
            reduction = ((original_size - processed_size) / original_size) * 100
            
            stats = {
                'original_size': original_shape,
                'processed_size': cleaned.shape,
                'noise_reduction': True,
                'contrast_enhanced': True,
                'text_optimized': True,
                'output_path': output_path,
                'file_size_reduction': round(reduction, 2)
            }
            
            return stats
            
        except Exception as e:
            raise ValidationException(f"Erro na otimização: {str(e)}")
    
    
    # ═════════════════════════════════════════════════════════
    # CRIAÇÃO DE THUMBNAILS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def create_thumbnail_variants(
        image_path: str, 
        sizes: List[Tuple[int, int]] = None
    ) -> Dict[str, str]:
        """
        Cria múltiplas versões de thumbnail.
        
        TAMANHOS PADRÃO:
        - 150x150: Ícone pequeno
        - 300x300: Preview médio
        - 600x600: Preview grande
        
        CARACTERÍSTICAS:
        - Mantém proporção
        - Corrige orientação EXIF
        - Otimiza qualidade
        
        Args:
            image_path: Caminho da imagem original
            sizes: Lista de tuplas (width, height)
            
        Returns:
            Dict com {tamanho: caminho}
            
        Exemplo:
            >>> thumbs = ImageProcessor.create_thumbnail_variants(
            ...     "questao.jpg",
            ...     sizes=[(150, 150), (300, 300)]
            ... )
            >>> thumbs
            {
                '150x150': 'path/to/thumb_150x150.jpg',
                '300x300': 'path/to/thumb_300x300.jpg'
            }
        """
        if sizes is None:
            sizes = [(150, 150), (300, 300), (600, 600)]
        
        thumbnails = {}
        
        try:
            with Image.open(image_path) as img:
                # Corrige orientação EXIF (fotos de celular)
                img = ImageOps.exif_transpose(img)
                
                base_path = Path(image_path)
                thumb_dir = base_path.parent / "thumbnails"
                thumb_dir.mkdir(exist_ok=True)
                
                for size in sizes:
                    # Cria cópia para thumbnail
                    thumb = img.copy()
                    
                    # Redimensiona mantendo proporção
                    thumb.thumbnail(size, Image.Resampling.LANCZOS)
                    
                    # Nome do arquivo
                    thumb_name = (
                        f"{base_path.stem}_thumb_{size[0]}x{size[1]}"
                        f"{base_path.suffix}"
                    )
                    thumb_path = thumb_dir / thumb_name
                    
                    # Configurações de salvamento
                    save_kwargs = {
                        'quality': ImageProcessor.QUALITY_THUMBNAIL,
                        'optimize': True
                    }
                    
                    # Salva no formato adequado
                    if base_path.suffix.lower() in ['.jpg', '.jpeg']:
                        thumb = thumb.convert('RGB')
                        thumb.save(thumb_path, 'JPEG', **save_kwargs)
                    else:
                        thumb.save(thumb_path, **save_kwargs)
                    
                    thumbnails[f"{size[0]}x{size[1]}"] = str(thumb_path)
            
            return thumbnails
            
        except Exception as e:
            raise ValidationException(f"Erro ao criar thumbnails: {str(e)}")
    
    
    # ═════════════════════════════════════════════════════════
    # DETECÇÃO DE TEXTO E SÍMBOLOS
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def extract_text_regions(image_path: str) -> List[Dict[str, Any]]:
        """
        Detecta e extrai regiões de texto da imagem.
        
        ALGORITMO:
        1. Binariza imagem
        2. Encontra contornos
        3. Filtra por tamanho e proporção
        4. Ordena por posição (top-to-bottom, left-to-right)
        
        USO: Detectar onde está o texto em uma questão
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            Lista de regiões encontradas:
            [
                {
                    'id': 0,
                    'bbox': (x, y, width, height),
                    'area': 1234,
                    'aspect_ratio': 3.5,
                    'center': (x_center, y_center)
                },
                ...
            ]
            
        Exemplo:
            >>> regions = ImageProcessor.extract_text_regions("questao.jpg")
            >>> len(regions)
            3
            >>> regions[0]['bbox']
            (10, 20, 300, 50)
        """
        try:
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Binarização com Otsu
            _, binary = cv2.threshold(
                gray, 0, 255, 
                cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            
            # Dilata para conectar caracteres próximos
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 3))
            dilated = cv2.dilate(binary, kernel, iterations=1)
            
            # Encontra contornos
            contours, _ = cv2.findContours(
                dilated, 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            text_regions = []
            for i, contour in enumerate(contours):
                # Calcula área
                area = cv2.contourArea(contour)
                
                # Filtra contornos muito pequenos
                if area < 100:
                    continue
                
                # Pega bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calcula proporção largura/altura
                aspect_ratio = w / float(h)
                
                # Filtra por proporção (texto é geralmente mais largo)
                if aspect_ratio < 0.5:  # Muito alto
                    continue
                
                text_regions.append({
                    'id': i,
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': round(aspect_ratio, 2),
                    'center': (x + w//2, y + h//2)
                })
            
            # Ordena por posição (de cima para baixo, esquerda para direita)
            text_regions.sort(key=lambda r: (r['bbox'][1], r['bbox'][0]))
            
            return text_regions
            
        except Exception as e:
            raise ValidationException(f"Erro na extração de texto: {str(e)}")
    
    
    @staticmethod
    def detect_mathematical_symbols(image_path: str) -> Dict[str, Any]:
        """
        Detecta símbolos matemáticos na imagem.
        
        DETECTA:
        - Círculos (pode ser +, ×, ÷)
        - Linhas horizontais (pode ser -, =)
        - Linhas verticais
        
        NOTA: Detecção básica. Para OCR completo, use Tesseract.
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            Dict com análise:
            {
                'total_symbols': 10,
                'has_equations': True,
                'symbols': [...]
            }
            
        Exemplo:
            >>> result = ImageProcessor.detect_mathematical_symbols("formula.jpg")
            >>> result['total_symbols']
            8
            >>> result['has_equations']
            True
        """
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            
            # Binariza
            _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Encontra contornos
            contours, _ = cv2.findContours(
                binary, 
                cv2.RETR_EXTERNAL, 
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            symbols = []
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filtra por tamanho
                if area < 50 or area > 5000:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calcula características
                aspect_ratio = w / float(h)
                extent = area / (w * h)  # Quanto do retângulo é preenchido
                
                # Classifica formato básico
                symbol_type = 'unknown'
                
                if 0.8 < aspect_ratio < 1.2 and extent > 0.7:
                    # Aproximadamente quadrado e preenchido
                    symbol_type = 'circle_like'  # Pode ser +, ×, ÷
                elif aspect_ratio > 2:
                    # Muito mais largo que alto
                    symbol_type = 'horizontal_line'  # Pode ser -, =
                elif aspect_ratio < 0.5:
                    # Muito mais alto que largo
                    symbol_type = 'vertical_line'
                
                symbols.append({
                    'bbox': (x, y, w, h),
                    'area': area,
                    'aspect_ratio': round(aspect_ratio, 2),
                    'extent': round(extent, 2),
                    'type': symbol_type
                })
            
            return {
                'total_symbols': len(symbols),
                'symbols': symbols,
                'has_equations': len(symbols) > 5  # Heurística simples
            }
            
        except Exception as e:
            raise ValidationException(f"Erro na detecção: {str(e)}")
    
    
    # ═════════════════════════════════════════════════════════
    # CONVERSÕES E UTILIDADES
    # ═════════════════════════════════════════════════════════
    
    @staticmethod
    def convert_to_base64(image_path: str) -> str:
        """
        Converte imagem para Base64 (para enviar via JSON).
        
        FORMATO: data:image/jpeg;base64,/9j/4AAQSkZJRgABA...
        
        USO: Enviar imagem via API sem upload de arquivo
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            String Base64 com prefixo de MIME type
            
        Exemplo:
            >>> b64 = ImageProcessor.convert_to_base64("foto.jpg")
            >>> b64[:30]
            'data:image/jpeg;base64,/9j/4A'
        """
        try:
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                base64_data = base64.b64encode(img_data).decode('utf-8')
                
                # Detecta MIME type pela extensão
                extension = Path(image_path).suffix.lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.svg': 'image/svg+xml'
                }
                
                mime_type = mime_types.get(extension, 'image/jpeg')
                
                return f"data:{mime_type};base64,{base64_data}"
                
        except Exception as e:
            raise ValidationException(f"Erro na conversão: {str(e)}")
    
    
    @staticmethod
    def get_image_info(image_path: str) -> Dict[str, Any]:
        """
        Obtém informações detalhadas da imagem.
        
        INFORMAÇÕES:
        - Dimensões (width, height)
        - Formato (JPEG, PNG, etc)
        - Modo de cor (RGB, RGBA, L)
        - Tamanho do arquivo
        - Dados EXIF (se disponível)
        - Proporção (aspect ratio)
        
        Args:
            image_path: Caminho da imagem
            
        Returns:
            Dict com todas as informações
            
        Exemplo:
            >>> info = ImageProcessor.get_image_info("foto.jpg")
            >>> info['width']
            1920
            >>> info['height']
            1080
            >>> info['aspect_ratio']
            1.78
            >>> info['file_size_formatted']
            '2.5 MB'
        """
        try:
            with Image.open(image_path) as img:
                # Informações básicas
                file_size = Path(image_path).stat().st_size
                
                info = {
                    'filename': Path(image_path).name,
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'aspect_ratio': round(img.width / img.height, 2),
                    'file_size': file_size,
                    'file_size_formatted': ImageProcessor._format_file_size(file_size)
                }
                
                # Informações EXIF (metadados de câmera)
                try:
                    exif = img.getexif()
                    if exif:
                        info['has_exif'] = True
                        # Apenas alguns campos importantes
                        info['exif_camera'] = exif.get(272, 'Unknown')  # Modelo
                        info['exif_datetime'] = exif.get(306, 'Unknown')  # Data
                    else:
                        info['has_exif'] = False
                except:
                    info['has_exif'] = False
                
                return info
                
        except Exception as e:
            raise ValidationException(f"Erro ao obter info: {str(e)}")
    
    
    @staticmethod
    def resize_image(
        image_path: str,
        max_width: int = None,
        max_height: int = None,
        output_path: str = None
    ) -> str:
        """
        Redimensiona imagem mantendo proporção.
        
        MODOS:
        - max_width + max_height: thumbnail dentro dos limites
        - max_width apenas: ajusta largura, altura proporcional
        - max_height apenas: ajusta altura, largura proporcional
        
        Args:
            image_path: Caminho original
            max_width: Largura máxima (opcional)
            max_height: Altura máxima (opcional)
            output_path: Onde salvar (None = gera nome automático)
            
        Returns:
            Caminho da imagem redimensionada
            
        Exemplo:
            >>> path = ImageProcessor.resize_image(
            ...     "foto.jpg",
            ...     max_width=800
            ... )
            >>> # Foto será redimensionada para 800px de largura
        """
        try:
            with Image.open(image_path) as img:
                original_size = img.size
                
                # Calcula novo tamanho
                if max_width and max_height:
                    # Thumbnail
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                elif max_width:
                    # Apenas largura
                    ratio = max_width / img.width
                    new_size = (max_width, int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                elif max_height:
                    # Apenas altura
                    ratio = max_height / img.height
                    new_size = (int(img.width * ratio), max_height)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Define caminho de saída
                if output_path is None:
                    output_path = image_path.replace('.', '_resized.')
                
                # Salva
                save_kwargs = {
                    'quality': ImageProcessor.QUALITY_STANDARD,
                    'optimize': True
                }
                
                if Path(image_path).suffix.lower() in ['.jpg', '.jpeg']:
                    img = img.convert('RGB')
                    img.save(output_path, 'JPEG', **save_kwargs)
                else:
                    img.save(output_path, **save_kwargs)
                
                return output_path
                
        except Exception as e:
            raise ValidationException(f"Erro ao redimensionar: {str(e)}")
    
    
    # ═════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES PRIVADOS
    # ═════════════════════════════════════════════════════════
     
    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Formata tamanho de arquivo em formato legível."""
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"


