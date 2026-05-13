"""
dsp/commands.py

Comandos para o módulo executor do carregador via arquivos DSV.

Interface mínima inicial:

  commands.dsv
      escrito pelo factory check
      formato: datetime; descrição; código

  commands_response.dsv
      escrito pelo módulo executor como ACK
      nesta etapa o factory check apenas registra em log se o ACK apareceu

Os comandos continuam sendo confirmados pelo operador nas fases 5 e 6.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)


COMMANDS = {
    "contactor_open":  ("abrir contatora", 21),
    "contactor_close": ("fechar contatora", 22),
    "fan_on":          ("ligar ventilador", 31),
    "fan_off":         ("desligar ventilador", 32),
}


def _timestamp() -> str:
    """Timestamp ISO com milissegundos, compatível com o padrão dos logs."""
    return datetime.now().isoformat(timespec="milliseconds")


def _write_command(description: str, code: int) -> bool:
    """
    Escreve o comando no arquivo commands.dsv.

    Usa escrita atômica via arquivo temporário + replace(), para reduzir o
    risco de o módulo executor ler uma linha parcialmente escrita.
    """
    command_path = Path(config.COMMAND_FILE)
    response_path = Path(config.COMMAND_RESPONSE_FILE)
    tmp_path = command_path.with_suffix(command_path.suffix + ".tmp")

    line = f"{_timestamp()}; {description}; {code}\n"

    try:
        # Remove ACK anterior para que a espera abaixo observe apenas uma
        # resposta nova referente ao comando recém-enviado.
        if response_path.exists():
            response_path.unlink()

        tmp_path.write_text(line, encoding="utf-8")
        tmp_path.replace(command_path)

        logger.info(
            f"Comando enviado ao módulo executor: "
            f"description='{description}' code={code} file='{command_path}'"
        )
        logger.debug(f"Linha escrita em {command_path}: {line.strip()}")

    except OSError as exc:
        logger.error(
            f"Falha ao escrever comando '{description}' code={code} "
            f"em {command_path}: {exc}"
        )
        return False

    _wait_for_ack(description, code, response_path)
    return True


def _wait_for_ack(description: str, code: int, response_path: Path) -> None:
    """
    Aguarda brevemente o ACK do módulo executor.

    O ACK não altera o fluxo das fases nesta etapa; ele apenas é registrado
    no log para diagnóstico.
    """
    deadline = time.monotonic() + float(config.COMMAND_ACK_TIMEOUT_S)

    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                content = response_path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                logger.warning(
                    f"ACK detectado para comando '{description}' code={code}, "
                    f"mas falhou leitura de {response_path}: {exc}"
                )
                return

            logger.info(
                f"ACK recebido do módulo executor para comando "
                f"'{description}' code={code}: {content!r}"
            )
            return

        time.sleep(float(config.COMMAND_ACK_POLL_S))

    logger.warning(
        f"ACK não recebido em {config.COMMAND_ACK_TIMEOUT_S:.1f}s para comando "
        f"'{description}' code={code}. O teste continuará aguardando "
        "confirmação do operador."
    )


def contactor_close(reader=None) -> bool:
    """Solicita fechamento da contatora ao módulo executor."""
    description, code = COMMANDS["contactor_close"]
    return _write_command(description, code)


def contactor_open(reader=None) -> bool:
    """Solicita abertura da contatora ao módulo executor."""
    description, code = COMMANDS["contactor_open"]
    return _write_command(description, code)


def fan_on(reader=None) -> bool:
    """Solicita acionamento do ventilador ao módulo executor."""
    description, code = COMMANDS["fan_on"]
    return _write_command(description, code)


def fan_off(reader=None) -> bool:
    """Solicita desligamento do ventilador ao módulo executor."""
    description, code = COMMANDS["fan_off"]
    return _write_command(description, code)
