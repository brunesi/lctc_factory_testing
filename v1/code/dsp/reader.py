"""
dsp/reader.py

Thread de leitura serial contínua do DSP.

Protocolo: binário com SOP(0x7E)/EOP(0x7D).
Leitura feita por dsp.protocol.read_binary_frame().
Decodificação feita por dsp.protocol.decode_megapayload().

Responsabilidades:
  - Ler frames binários continuamente
  - Atualizar DspState (com threading.Lock)
  - Detectar bordas nos botões → ButtonEvent na Queue
  - Expor send() para comandos thread-safe
"""

import queue
import threading
import logging
from datetime import datetime
from dataclasses import dataclass

import serial

from dsp.state import DspState
from dsp.protocol import (
    read_binary_frame,
    decode_megapayload,
    FUNCTION_MEGAPAYLOAD,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Evento de botão                                                     #
# ------------------------------------------------------------------ #

@dataclass
class ButtonEvent:
    button: int               # 1, 2, 3 ou 4
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ------------------------------------------------------------------ #
# Thread de leitura                                                   #
# ------------------------------------------------------------------ #

class DspReader(threading.Thread):
    """
    Thread daemon que lê frames binários da serial continuamente,
    atualiza DspState e publica ButtonEvents na fila.

    Expõe send() para que commands.py escreva na mesma porta
    serial sem conflito com a leitura contínua.
    """

    def __init__(
        self,
        port: str,
        baud: int,
        state: DspState,
        event_queue: queue.Queue,
    ):
        super().__init__(daemon=True, name="DspReader")
        self.port        = port
        self.baud        = baud
        self.state       = state
        self.event_queue = event_queue

        self._stop_event  = threading.Event()
        self._write_lock  = threading.Lock()
        self._ser: serial.Serial | None = None

        # Estado anterior dos botões para detecção de borda
        self._prev_buttons = "0000"

    # ---------------------------------------------------------------- #
    # Interface pública                                                 #
    # ---------------------------------------------------------------- #

    def stop(self):
        self._stop_event.set()

    def send(self, stream: bytes) -> bool:
        """
        Envia bytes na porta serial já aberta pela thread.
        Thread-safe via _write_lock.
        Retorna True se enviado com sucesso.
        """
        with self._write_lock:
            if self._ser is None or not self._ser.is_open:
                logger.error("send() chamado com porta serial fechada.")
                return False
            try:
                self._ser.write(stream)
                return True
            except serial.SerialException as e:
                logger.error(f"Erro ao escrever na serial: {e}")
                return False

    # ---------------------------------------------------------------- #
    # Loop principal da thread                                          #
    # ---------------------------------------------------------------- #

    def run(self):
        logger.info(f"DspReader iniciando em {self.port} @ {self.baud}")

        while not self._stop_event.is_set():
            try:
                with serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    timeout=10,
                ) as ser:
                    ser.dtr = False   # de-assert → nível 1 (equivalente a set_dtr(False))
                    ser.rts = False   # de-assert → nível 1
                    self._ser = ser
                    logger.info("Porta serial aberta.")

                    while not self._stop_event.is_set():
                        result = read_binary_frame(ser)

                        if result is None:
                            # Frame inválido ou timeout — continua
                            continue

                        function_code, payload = result

                        if function_code == FUNCTION_MEGAPAYLOAD:
                            decoded = decode_megapayload(payload)
                            if decoded:
                                self._update_state(decoded)
                                self._detect_button_edges()
                        else:
                            logger.debug(
                                f"Frame ignorado: function=0x{function_code:02X}"
                            )

            except serial.SerialException as e:
                logger.error(f"Erro serial: {e}. Tentando reconectar em 3s.")
                self._ser = None
                self._stop_event.wait(timeout=3)

        self._ser = None
        logger.info("DspReader encerrado.")

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _update_state(self, decoded: dict) -> None:
        """Atualiza DspState a partir do dict decodificado."""
        with self.state.lock:
            self.state.frame_valid        = True
            self.state.charge_state       = decoded["charge_state"]
            self.state.connector          = decoded["connector"]
            self.state.posix              = decoded["posix"]
            self.state.voltage            = decoded["voltage"]
            self.state.current            = decoded["current"]
            self.state.current_requested  = decoded["current_requested"]
            self.state.soc                = decoded["soc"]
            self.state.charge_duration    = decoded["charge_duration"]
            self.state.battery_voltage    = decoded["battery_voltage"]
            self.state.energy_accumulated = decoded["energy_accumulated"]
            self.state.fan_status         = decoded["fan_status"]
            self.state.t1_dsp             = decoded["t1_dsp"]
            self.state.t2_board           = decoded["t2_board"]
            self.state.t3_rack            = decoded["t3_rack"]
            self.state.t4_cable1          = decoded["t4_cable1"]
            self.state.t5_cable2          = decoded["t5_cable2"]
            self.state.raw_payload_hex    = decoded.get("raw_payload_hex", "")
            self.state.raw_data_hex       = decoded.get("raw_data_hex", "")
            self.state.raw_temperature_window_hex = decoded.get("raw_temperature_window_hex", "")
            self.state.raw_t1_t5_positions_hex = decoded.get("raw_t1_t5_positions_hex", {})

            if self.state.t4_cable1 == 0 or self.state.t5_cable2 == 0:
                logger.info(
                    "Temperatura de cabo zerada no frame recebido: "
                    f"T1={self.state.t1_dsp} T2={self.state.t2_board} "
                    f"T3={self.state.t3_rack} T4={self.state.t4_cable1} "
                    f"T5={self.state.t5_cable2}; "
                    f"raw d[24:33]={decoded.get('raw_temperature_window_hex', '')}; "
                    f"raw positions={decoded.get('raw_t1_t5_positions_hex', {})}"
                )

            self.state.buttons_raw        = decoded["buttons_raw"]
            self.state.emergency          = decoded["emergency"]
            self.state.leakage_current    = decoded["leakage_current"]
            self.state.output_resistance  = decoded["output_resistance"]
            self.state.digital_raw        = decoded["digital_raw"]
            self.state.ax                 = decoded["ax"]
            self.state.ay                 = decoded["ay"]
            self.state.az                 = decoded["az"]
            self.state.last_updated       = datetime.now()

    def _detect_button_edges(self) -> None:
        """
        Compara estado atual dos botões com o anterior.
        Publica ButtonEvent na fila para cada transição 0→1.
        String "4321": índice 0=B4, 1=B3, 2=B2, 3=B1.
        """
        with self.state.lock:
            current = self.state.buttons_raw

        for i, (prev, curr) in enumerate(zip(self._prev_buttons, current)):
            if prev == "0" and curr == "1":
                button_number = 4 - i   # índice 0→B4, 3→B1
                event = ButtonEvent(button=button_number)
                self.event_queue.put(event)
                logger.debug(f"ButtonEvent: B{button_number} pressionado")

        self._prev_buttons = current
