"""Serviços de email."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
 

class EmailService:
    """Serviços de email."""
     
    @staticmethod
    def send_email(
        to_emails: List[str],
        subject: str,
        body: str,
        is_html: bool = False
    ) -> bool:
        """Envia email."""
        
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.warning("Configurações de email não definidas")
            return False
        
        try:
            # Cria mensagem
            msg = MIMEMultipart()
            msg['From'] = settings.EMAIL_FROM or settings.SMTP_USER
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            # Corpo da mensagem
            msg_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, msg_type))
            
            # Conecta ao servidor SMTP
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            # Envia email
            text = msg.as_string()
            server.sendmail(settings.SMTP_USER, to_emails, text)
            server.quit()
            
            logger.info(f"Email enviado com sucesso para: {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    @staticmethod
    def send_verification_email(email: str, token: str) -> bool:
        """Envia email de verificação."""
        subject = "Verificação de Email - Olimpíadas de Matemática"
        
        # URL de verificação (deve ser configurada conforme seu frontend)
        verify_url = f"{settings.CORS_ORIGINS[0]}/verify-email/{token}"
        
        body = f"""
        <h2>Verificação de Email</h2>
        <p>Clique no link abaixo para verificar seu email:</p>
        <a href="{verify_url}">Verificar Email</a>
        <p>Se você não criou esta conta, pode ignorar este email.</p>
        <br>
        <p>Equipe Olimpíadas de Matemática</p>
        """
        
        return EmailService.send_email([email], subject, body, is_html=True)
    
    @staticmethod
    def send_password_reset_email(email: str, token: str) -> bool:
        """Envia email de reset de senha."""
        subject = "Reset de Senha - Olimpíadas de Matemática"
        
        # URL de reset (deve ser configurada conforme seu frontend)
        reset_url = f"{settings.CORS_ORIGINS[0]}/reset-password/{token}"
        
        body = f"""
        <h2>Reset de Senha</h2>
        <p>Você solicitou o reset de sua senha.</p>
        <p>Clique no link abaixo para criar uma nova senha:</p>
        <a href="{reset_url}">Resetar Senha</a>
        <p>Este link expira em 1 hora.</p>
        <p>Se você não solicitou este reset, pode ignorar este email.</p>
        <br>
        <p>Equipe Olimpíadas de Matemática</p>
        """
        
        return EmailService.send_email([email], subject, body, is_html=True)
    
    @staticmethod
    def send_welcome_email(email: str, name: str) -> bool:
        """Envia email de boas-vindas."""
        subject = "Bem-vindo às Olimpíadas de Matemática!"
        
        body = f"""
        <h2>Bem-vindo, {name}!</h2>
        <p>Sua conta foi criada com sucesso.</p>
        <p>Você já pode começar a criar e gerenciar questões matemáticas.</p>
        <p>Se tiver dúvidas, entre em contato conosco.</p>
        <br>
        <p>Equipe Olimpíadas de Matemática</p>
        """
        
        return EmailService.send_email([email], subject, body, is_html=True)