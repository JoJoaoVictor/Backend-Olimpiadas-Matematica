"""Script para backup do banco de dados."""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import os

sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_backup():
    """Cria backup do banco PostgreSQL."""
    logger.info("💾 Iniciando backup do banco de dados...")
    
    # Parse da URL do banco
    db_url = settings.DATABASE_URL
    if not db_url.startswith('postgresql'):
        logger.error("❌ Apenas PostgreSQL é suportado para backup!")
        return
    
    # Extrai componentes da URL
    # postgresql://user:pass@host:port/dbname
    url_parts = db_url.replace('postgresql://', '').split('/')
    db_name = url_parts[-1]
    host_part = url_parts[0].split('@')
    
    if len(host_part) == 2:
        user_pass = host_part[0]
        host_port = host_part[1]
        
        if ':' in user_pass:
            user, password = user_pass.split(':', 1)
        else:
            user = user_pass
            password = ""
        
        if ':' in host_port:
            host, port = host_port.split(':', 1)
        else:
            host = host_port
            port = "5432"
    else:
        logger.error("❌ Formato de URL do banco inválido!")
        return
    
    # Nome do arquivo de backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"olimpiadas_backup_{timestamp}.sql"
    
    # Comando pg_dump
    cmd = [
        "pg_dump",
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", db_name,
        "-f", str(backup_file),
        "--verbose",
        "--no-password"
    ]
    
    # Define senha via variável de ambiente
    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password
    
    try:
        logger.info(f"📁 Salvando backup em: {backup_file}")
        
        result = subprocess.run(
            cmd, 
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("✅ Backup criado com sucesso!")
        logger.info(f"   Arquivo: {backup_file}")
        logger.info(f"   Tamanho: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
        
        # Comprime o backup
        logger.info("🗜️ Comprimindo backup...")
        
        gzip_cmd = ["gzip", str(backup_file)]
        subprocess.run(gzip_cmd, check=True)
        
        compressed_file = Path(str(backup_file) + ".gz")
        logger.info(f"✅ Backup comprimido: {compressed_file}")
        logger.info(f"   Tamanho final: {compressed_file.stat().st_size / 1024 / 1024:.2f} MB")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro ao criar backup: {e}")
        logger.error(f"   Stdout: {e.stdout}")
        logger.error(f"   Stderr: {e.stderr}")
    except FileNotFoundError:
        logger.error("❌ pg_dump não encontrado! Instale PostgreSQL client tools.")


def restore_backup():
    """Restaura backup do banco.""" 
    if len(sys.argv) < 3:
        logger.error("❌ Uso para restore: python backup_database.py restore <arquivo_backup>")
        return
    
    backup_file = sys.argv[2]
    if not Path(backup_file).exists():
        logger.error(f"❌ Arquivo de backup não encontrado: {backup_file}")
        return
    
    logger.warning("⚠️ ATENÇÃO: Esta operação irá SOBRESCREVER o banco atual!")
    confirm = input("Digite 'CONFIRMO' para continuar: ")
    
    if confirm != "CONFIRMO":
        logger.info("❌ Operação cancelada.")
        return
    
    logger.info(f"🔄 Restaurando backup de {backup_file}...")
    
    # TODO: Implementar lógica de restore
    logger.info("🚧 Funcionalidade de restore em desenvolvimento...")
 

def main():
    """Função principal."""
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_backup()
    else:
        create_backup()


if __name__ == "__main__":
    main()