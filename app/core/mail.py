import logging
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_mail_config() -> ConnectionConfig | None:
    """
    Retorna a configuração de e‑mail ou None se estiver em desenvolvimento
    e as credenciais não estiverem completas.
    Em produção, exige que todas as variáveis estejam preenchidas.
    """
    required_fields = ["MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_SERVER"]
    missing = [f for f in required_fields if not getattr(settings, f)]

    if missing:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                f"Configuração de e‑mail incompleta em produção. Campos faltantes: {missing}"
            )
        else:
            logger.warning(
                f"⚠️ Configuração de e‑mail ausente ({missing}). "
                f"E‑mails não serão enviados (apenas logados)."
            )
            return None

    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=settings.ENVIRONMENT == "production",
    )


async def send_reset_password_email(email_to: str, link: str):
    """
    Envia o email de recuperação de senha.
    Em desenvolvimento, apenas loga o link.
    """
    conf = _get_mail_config()
    if conf is None:
        # Fallback para desenvolvimento: log estruturado
        logger.info(f"[DEV] Link de recuperação para {email_to}: {link}")
        return

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
        <h2 style="color: #4A90E2; text-align: center;">Recuperação de Senha</h2>
        <p>Olá,</p>
        <p>Recebemos uma solicitação para redefinir sua senha.</p>
        <p>Clique no botão abaixo para criar uma nova senha:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}" style="background-color: #4A90E2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Redefinir Minha Senha
            </a>
        </div>
        
        <p>Ou copie e cole o link abaixo no seu navegador:</p>
        <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; color: #666; font-size: 12px; word-break: break-all;">{link}</p>
        
        <p><i>Este link expira em 30 minutos.</i></p>
    </div>
    """

    message = MessageSchema(
        subject="Redefinição de Senha - Olimpíadas Matemática",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    logger.info(f"E‑mail de recuperação enviado para {email_to}")