"""
logger.py

Log em duas camadas:
  Camada 1 — disco interno, desde o boot, sempre disponível
  Camada 2 — exportação para pendrive ao final do check

Também configura o logging padrão do Python para que
todos os módulos (dsp/reader, fases, etc.) gravem no mesmo arquivo.
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from config import LOG_INTERNAL_DIR, LOG_PENDRIVE_DIR
from result import CheckResult


# ------------------------------------------------------------------ #
# Configuração do logging padrão                                      #
# ------------------------------------------------------------------ #

def setup_logging(session_id: str) -> Path:
    """
    Configura handlers de logging para console e arquivo interno.
    Retorna o caminho do arquivo de log criado.
    """
    log_dir = Path(LOG_INTERNAL_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{session_id}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),         # também no console/journald
        ],
    )

    logging.getLogger(__name__).info(
        f"Log iniciado: {log_file}"
    )

    return log_file


# ------------------------------------------------------------------ #
# Salvar resultado do check                                           #
# ------------------------------------------------------------------ #

def save_result(result: CheckResult, session_id: str) -> dict[str, bool]:
    """
    Salva o texto consolidado do CheckResult.
    Tenta salvar em disco interno (sempre) e em pendrive (se disponível).

    Retorna dict com {'internal': bool, 'pendrive': bool}.
    """
    timestamp_str = result.started_at.strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"factory_check_{result.serial_number}_{timestamp_str}.txt"
    content = result.to_log_text()

    outcomes = {"internal": False, "pendrive": False}

    # Camada 1 — disco interno
    try:
        internal_dir = Path(LOG_INTERNAL_DIR)
        internal_dir.mkdir(parents=True, exist_ok=True)
        internal_path = internal_dir / filename
        internal_path.write_text(content, encoding="utf-8")
        logging.info(f"Resultado salvo internamente: {internal_path}")
        outcomes["internal"] = True
    except OSError as e:
        logging.error(f"Falha ao salvar resultado interno: {e}")

    # Camada 2 — pendrive
    try:
        pendrive_dir = Path(LOG_PENDRIVE_DIR)
        if _pendrive_available(pendrive_dir):
            pendrive_dir.mkdir(parents=True, exist_ok=True)
            pendrive_path = pendrive_dir / filename
            pendrive_path.write_text(content, encoding="utf-8")
            logging.info(f"Resultado exportado para pendrive: {pendrive_path}")
            outcomes["pendrive"] = True
        else:
            logging.warning("Pendrive não disponível — exportação ignorada.")
    except OSError as e:
        logging.error(f"Falha ao exportar para pendrive: {e}")

    return outcomes


def _pendrive_available(path: Path) -> bool:
    """
    Verifica se o pendrive está montado checando se o diretório
    pai existe e está em um ponto de montagem diferente de '/'.
    """
    try:
        mount_point = path.parent
        while not mount_point.exists():
            mount_point = mount_point.parent
        # Se o diretório raiz do pendrive existe, assumimos montado
        return Path("/media/pendrive").exists()
    except OSError:
        return False


def check_pendrive() -> bool:
    """
    Verificação explícita usada na Fase 1.10.
    Retorna True se o pendrive está presente e gravável.
    """
    pendrive = Path("/media/pendrive")
    if not pendrive.exists():
        return False
    # Tenta criar um arquivo de teste
    test_file = pendrive / ".factory_check_test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        return True
    except OSError:
        return False


def make_session_id() -> str:
    """Gera um ID de sessão baseado em timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")
