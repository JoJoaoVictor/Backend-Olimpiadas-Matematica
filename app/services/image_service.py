"""Serviços de processamento de imagens."""

import os
import uuid
from typing import Optional, Tuple
from pathlib import Path
from PIL import Image, ImageOps
import shutil

from app.database import SessionLocal
from datetime import datetime, timedelta
from app.models.question import Question # 🌟 Precisamos importar o modelo de Questão

from app.models.image import Image as ImageModel
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import ValidationException


class ImageService:
    """Serviços de imagens."""
    
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.svg'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DIMENSION = 2048
    
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
            
            # Remove do banco
            db.delete(image)
            db.commit()
            
            return True
            
        except Exception:
            return False

    @staticmethod
    def clean_orphan_images() -> None:
        db = SessionLocal()

        try:
            # Limite para testes (5 segundos). Depois mude para timedelta(hours=2)
            time_limit = datetime.utcnow() - timedelta(seconds=5)

            # 1. Pega todos os IDs de imagens que estão sendo usadas em alguma questão
            used_image_ids = db.query(Question.image_id).filter(Question.image_id.isnot(None)).subquery()
            
            # 2. Busca todas as imagens cujo ID *NÃO* está nessa lista e que já passaram do tempo
            orphans = db.query(ImageModel).filter(
                ~ImageModel.id.in_(used_image_ids),
                ImageModel.created_at < time_limit
            ).all()

            count_deleted = 0

            for image in orphans:
                try:
                    # Tenta apagar o arquivo físico no HD
                    file_path = Path(settings.UPLOAD_PATH) / image.file_path
                    if file_path.exists():
                        file_path.unlink()
                    
                    # Apaga o registro do banco de dados
                    db.delete(image)
                    count_deleted += 1

                except Exception as e:
                    print(f"⚠️ Erro ao remover o arquivo físico da imagem {image.id}: {str(e)}")
                    continue 

            # Efetiva as exclusões no banco
            if count_deleted > 0:
                db.commit()
                # Usando print para garantir que apareça no terminal do Uvicorn!
                print(f"🧹 SUCESSO! Limpeza Automática: {count_deleted} imagens órfãs foram apagadas do banco.")

        except Exception as e:
            db.rollback()
            print(f"❌ Erro fatal na limpeza em segundo plano: {str(e)}")
        finally:
            db.close()