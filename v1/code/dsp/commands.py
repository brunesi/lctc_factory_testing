"""
dsp/commands.py

Funções para enviar comandos ao DSP via porta serial.
Cada comando é uma chamada pontual — o DSP não confirma
recebimento, portanto o resultado é sempre verificado
por telemetria ou confirmação do operador.

Expansível: adicionar novos comandos conforme o protocolo
proprietário for documentado.
"""

import logging
import serial

logger = logging.getLogger(__name__)


def _send(port: str, baud: int, payload: bytes) -> bool:
    """
    Abre a porta, envia payload e fecha.
    Retorna True se enviado sem exceção.
    """
    try:
        with serial.Serial(port=port, baudrate=baud, timeout=2) as ser:
            ser.write(payload)
            logger.debug(f"Comando enviado: {payload.hex()}")
            return True
    except serial.SerialException as e:
        logger.error(f"Falha ao enviar comando: {e}")
        return False


def contactor_close(port: str, baud: int) -> bool:
    """Fecha a contatora."""
    # TODO: substituir pelo payload real do protocolo proprietário
    payload = bytes([0x01, 0x01])
    logger.info("Comando: fechar contatora")
    return _send(port, baud, payload)


def contactor_open(port: str, baud: int) -> bool:
    """Abre a contatora."""
    # TODO: substituir pelo payload real do protocolo proprietário
    payload = bytes([0x01, 0x00])
    logger.info("Comando: abrir contatora")
    return _send(port, baud, payload)


def fan_on(port: str, baud: int) -> bool:
    """Liga o ventilador."""
    # TODO: substituir pelo payload real do protocolo proprietário
    payload = bytes([0x02, 0x01])
    logger.info("Comando: ligar ventilador")
    return _send(port, baud, payload)


def fan_off(port: str, baud: int) -> bool:
    """Desliga o ventilador."""
    # TODO: substituir pelo payload real do protocolo proprietário
    payload = bytes([0x02, 0x00])
    logger.info("Comando: desligar ventilador")
    return _send(port, baud, payload)
