"""Serviços de processamento de imagens."""

import os
import uuid
from typing import Optional, Tuple
from pathlib import Path
from PIL import Image, ImageOps
import shutil

from app.models.image import Image as ImageModel
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import ValidationException


class ImageService:
    """Serviços de imagens."""
    
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.svg'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DIMENSION = 2048
    THUMBNAIL_SIZE = (300, 300)
    
    @staticmethod
    def upload_image(
        db,
        file,
        current_user: User,
        description: Optional[str] = None
    ) -> ImageModel:
        """Upload e processamento de imagem."""
        
        # Validações básicas
        ImageService._validate_file(file)
        
        # Gera nome único
        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        
        # Diretórios
        upload_dir = Path(settings.UPLOAD_PATH) / "images"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / unique_filename
        
        try:
            # Salva arquivo temporariamente
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Processa imagem
            processed_info = ImageService._process_image(file_path)
            
            # Cria thumbnail
            thumbnail_path = ImageService._create_thumbnail(file_path)
            
            # Salva no banco
            image_model = ImageModel(
                filename=unique_filename,
                original_name=file.filename,
                file_path=str(file_path.relative_to(Path(settings.UPLOAD_PATH))),
                file_size=file_path.stat().st_size,
                mime_type=file.content_type,
                width=processed_info['width'],
                height=processed_info['height'],
                url=f"/uploads/images/{unique_filename}",
                thumbnail_url=f"/uploads/images/thumbnails/{thumbnail_path.name}" if thumbnail_path else None
            )
            
            db.add(image_model)
            db.commit()
            db.refresh(image_model)
            
            return image_model
            
        except Exception as e:
            # Remove arquivo se houver erro
            if file_path.exists():
                file_path.unlink()
            raise ValidationException(f"Erro no upload da imagem: {str(e)}")
    
    @staticmethod
    def _validate_file(file) -> None:
        """Valida arquivo de imagem."""
        # Verifica extensão
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ImageService.ALLOWED_EXTENSIONS:
            raise ValidationException(
                f"Extensão não permitida. Use: {', '.join(ImageService.ALLOWED_EXTENSIONS)}"
            )
        
        # Verifica tamanho (aproximado)
        file.file.seek(0, 2)  # Vai para o final
        file_size = file.file.tell()
        file.file.seek(0)  # Volta para o início
        
        if file_size > ImageService.MAX_FILE_SIZE:
            raise ValidationException(
                f"Arquivo muito grande. Máximo: {ImageService.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Verifica tipo MIME
        allowed_mimes = {
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/gif', 'image/svg+xml'
        }
        if file.content_type not in allowed_mimes:
            raise ValidationException("Tipo de arquivo não permitido")
    
    @staticmethod
    def _process_image(file_path: Path) -> dict:
        """Processa e otimiza imagem."""
        try:
            with Image.open(file_path) as img:
                # Informações originais
                original_width, original_height = img.size
                
                # Corrige orientação EXIF
                img = ImageOps.exif_transpose(img)
                
                # Redimensiona se necessário
                if img.width > ImageService.MAX_DIMENSION or img.height > ImageService.MAX_DIMENSION:
                    img.thumbnail((ImageService.MAX_DIMENSION, ImageService.MAX_DIMENSION), Image.Resampling.LANCZOS)
                
                # Otimiza e salva
                if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                    img = img.convert('RGB')
                    img.save(file_path, 'JPEG', quality=85, optimize=True)
                elif file_path.suffix.lower() == '.png':
                    img.save(file_path, 'PNG', optimize=True)
                
                return {
                    'width': img.width,
                    'height': img.height,
                    'original_width': original_width,
                    'original_height': original_height
                }
                
        except Exception as e:
            raise ValidationException(f"Erro no processamento da imagem: {str(e)}")
    
    @staticmethod
    def _create_thumbnail(file_path: Path) -> Optional[Path]:
        """Cria thumbnail da imagem."""
        try:
            # Diretório de thumbnails
            thumb_dir = file_path.parent / "thumbnails"
            thumb_dir.mkdir(exist_ok=True)
            
            thumb_path = thumb_dir / f"thumb_{file_path.name}"
            
            with Image.open(file_path) as img:
                # Corrige orientação
                img = ImageOps.exif_transpose(img)
                
                # Cria thumbnail mantendo proporção
                img.thumbnail(ImageService.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                
                # Salva thumbnail
                if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                    img = img.convert('RGB')
                    img.save(thumb_path, 'JPEG', quality=80, optimize=True)
                elif file_path.suffix.lower() == '.png':
                    img.save(thumb_path, 'PNG', optimize=True)
                
                return thumb_path
                
        except Exception:
            return None  # Falha na criação do thumbnail não é crítica
    
    @staticmethod
    def delete_image(db, image_id: int, current_user: User) -> bool:
        """Remove imagem e arquivos."""
        image = db.query(ImageModel).filter(ImageModel.id == image_id).first()
        if not image:
            return False
        
        try:
            # Remove arquivos
            file_path = Path(settings.UPLOAD_PATH) / image.file_path
            if file_path.exists():
                file_path.unlink()
            
            # Remove thumbnail
            if image.thumbnail_url:
                thumb_path = Path(settings.UPLOAD_PATH) / image.thumbnail_url.lstrip("/uploads/")
                if thumb_path.exists():
                    thumb_path.unlink()
            
            # Remove do banco
            db.delete(image)
            db.commit()
            
            return True
            
        except Exception:
            return False

 