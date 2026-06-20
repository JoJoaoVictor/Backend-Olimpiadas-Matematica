"""
Serviços de gerenciamento de usuários (Lógica de Negócio).
Arquivo: app/services/user_service.py
"""

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_password_hash
# Imports dos Models e Schemas
from app.models.user import User, UserRole
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserUpdate, UserRoleUpdate


class UserService:
    """
    Classe contendo toda a lógica de manipulação de usuários.
    Encapsula o acesso ao banco (SQLAlchemy).
    """

    #  Mapeamento estrito para blindar o preenchimento de Cidade a partir do Campus/Polo
    CAMPUS_CIDADE_MAP = {
        "ALTA_FLORESTA": "Alta Floresta",
        "BARRA_DO_BUGRES": "Barra do Bugres",
        "CACERES": "Cáceres",
        "COLIDER": "Colíder",
        "DIAMANTINO": "Diamantino",
        "GUARANTA_DO_NORTE": "Guarantã do Norte",
        "JUARA": "Juara",
        "JUINA": "Juína",
        "NOVA_MUTUM": "Nova Mutum",
        "NOVA_XAVANTINA": "Nova Xavantina",
        "PONTES_E_LACERDA": "Pontes e Lacerda",
        "SINOP": "Sinop",
        "TANGARA_DA_SERRA": "Tangará da Serra",
        
        "ALTO_PARAGUAI": "Alto Paraguai",
        "NORTELANDIA": "Nortelândia",
        "NOVA_MARILANDIA": "Nova Marilândia",
        "NOVA_OLIMPIA": "Nova Olímpia",
        "PORTO_ESTRELA": "Porto Estrela",
        
        "CAMPO_NOVO_DO_PARECIS": "Campo Novo do Parecis",
        "CARLINDA": "Carlinda",
        "ITANHANGA": "Itanhangá",
        "ITAUBA": "Itaúba",
        "LUCAS_DO_RIO_VERDE": "Lucas do Rio Verde",
        "MARCELANDIA": "Marcelândia",
        "NOVA_CANAA_DO_NORTE": "Nova Canaã do Norte",
        "NOVA_MONTE_VERDE": "Nova Monte Verde",
        "NOVA_SANTA_HELENA": "Nova Santa Helena",
        "PARANAITA": "Paranaíta",
        "PORTO_DOS_GAUCHOS": "Porto dos Gaúchos",
        "TABAPORA": "Tabaporã",
        "TAPURAH": "Tapurah",
        "TERRA_NOVA_DO_NORTE": "Terra Nova do Norte"
    }

    @staticmethod
    def update_user_profile(db: Session, user_id: int, user_data: dict) -> User:
        """
        Atualiza os dados cadastrais do próprio usuário logado.
        Agora aceita a Cidade como um campo de texto livre e independente do Campus.
        """
        user = db.query(User).options(joinedload(User.profile)).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )

        # 1. Atualização dos dados da tabela primária (User)
        if "name" in user_data and user_data["name"] is not None:
            user.name = user_data["name"].strip()
        if "avatar_url" in user_data and user_data["avatar_url"] is not None:
            user.avatar_url = user_data["avatar_url"].strip()

        # 2. Atualização dos dados da tabela secundária (UserProfile)
        profile_data = user_data.get("profile")
        if profile_data:
            if not user.profile:
                user.profile = UserProfile(user_id=user.id)
                db.add(user.profile)
 
            fields_to_update = ["telefone", "matricula", "curso", "cpf", "cidade", "campus"]
            
            for field in fields_to_update:
                if field in profile_data:
                    val = profile_data[field]
                    if isinstance(val, str) and not val.strip():
                        val = None
                    setattr(user.profile, field, val)

            # ❌ Toda a "Inteligência de Geolocalização do Campus" que sobreescrevia 
            # a cidade forçadamente foi removida daqui, pois o frontend agora envia a string correta.

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def create_user(db: Session, user_data: UserCreate, current_user: User) -> User:
        """Cria novo usuário (Apenas Admin)."""
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já está em uso"
            )
        
        user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            role=user_data.role or UserRole.STUDENT,
            is_active=user_data.is_active if user_data.is_active is not None else True,
            is_email_verified=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """Lista usuários aplicando filtros de busca."""
        query = db.query(User).options(joinedload(User.profile))
        
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Busca usuário por ID."""
        user = db.query(User).options(joinedload(User.profile)).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        return user
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Busca usuário por email (interno)."""
        return db.query(User).filter(User.email == email).first()
      
    @staticmethod
    def update_user(
        db: Session, 
        user_id: int, 
        user_data: UserUpdate,
        current_user: User
    ) -> User:
        """Atualiza dados gerais do usuário."""
        user = UserService.get_user_by_id(db, user_id)
        update_data = user_data.dict(exclude_unset=True)
        
        if "email" in update_data and update_data["email"] != user.email:
             exists = db.query(User).filter(User.email == update_data["email"]).first()
             if exists:
                 raise HTTPException(status_code=400, detail="Email já em uso.")

        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user_role(
        db: Session,
        user_id: int,
        role_data: UserRoleUpdate,
        current_user: User
    ) -> User:
        """Atualiza APENAS o cargo do usuário."""
        user = UserService.get_user_by_id(db, user_id)
        
        if user.id == current_user.id:
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail="Você não pode alterar seu próprio cargo nesta rota."
             )

        user.role = role_data.role
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> User:
        """Remove usuário (Soft Delete ou Hard Delete)."""
        user = UserService.get_user_by_id(db, user_id)
        
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível deletar sua própria conta"
            )
        
        user.is_active = False
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_user_stats(db: Session) -> Dict[str, Any]:
        """Gera estatísticas para o dashboard."""
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        roles_count = db.query(User.role, func.count(User.role)).group_by(User.role).all()
        roles_dict = {role.value: count for role, count in roles_count}
        
        return {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "by_role": roles_dict
        }