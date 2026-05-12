"""
dsp/reader.py

Thread de leitura contínua da telemetria DSP publicada no journal do
chargepoint.service.

Fonte de dados:

    journalctl -u chargepoint.service --since "30 seconds ago" -o cat -f | grep "04 64"

Responsabilidades:
  - Acompanhar linhas 04 64 no journal
  - Decodificar a linha textual com dsp.protocol.parse_journal_frame()
  - Atualizar DspState (com threading.Lock)
  - Detectar bordas nos botões → ButtonEvent na Queue
  - Expor send() como placeholder temporário para comandos futuros
"""

import os
import queue
import threading
import logging
import subprocess
from datetime import datetime
from dataclasses import dataclass

from dsp.state import DspState
from dsp.protocol import parse_journal_frame

logger = logging.getLogger(__name__)


JOURNAL_COMMAND = [
    "journalctl",
    "-u",
    "chargepoint.service",
    "--since",
    "30 seconds ago",
    "-o",
    "cat",
    "-f",
]

GREP_PATTERN = "04 64"


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
    Thread daemon que lê linhas 04 64 do journal continuamente,
    atualiza DspState e publica ButtonEvents na fila.

    O método send() permanece como placeholder temporário para manter a
    interface usada pelas fases de comando. A implementação real dos
    comandos será atualizada separadamente.
    """

    def __init__(
        self,
        state: DspState,
        event_queue: queue.Queue,
    ):
        super().__init__(daemon=True, name="DspReader")
        self.state       = state
        self.event_queue = event_queue

        self._stop_event = threading.Event()
        self._process: subprocess.Popen | None = None

        # Estado anterior dos botões para detecção de borda.
        # Mapeamento físico validado na Fase 02:
        #   buttons_raw[0] = B1
        #   buttons_raw[1] = B2
        #   buttons_raw[2] = B3
        #   buttons_raw[3] = B4
        self._prev_buttons = "0000"

    # ---------------------------------------------------------------- #
    # Interface pública                                                 #
    # ---------------------------------------------------------------- #

    def stop(self):
        self._stop_event.set()
        self._terminate_process()

    def send(self, stream: bytes) -> bool:
        """
        Placeholder temporário para envio de comandos ao DSP.

        A entrada de telemetria foi migrada da serial para o journal.
        A saída de comandos será definida em uma próxima etapa.
        """
        logger.warning(
            "DspReader.send() chamado, mas envio de comandos ainda não "
            "foi implementado nesta versão via journal."
        )
        return False

    # ---------------------------------------------------------------- #
    # Loop principal da thread                                          #
    # ---------------------------------------------------------------- #

    def run(self):
        logger.info(
            "DspReader iniciando leitura do journal: "
            + " ".join(JOURNAL_COMMAND)
            + f" | filtro Python {GREP_PATTERN!r}"
        )

        while not self._stop_event.is_set():
            try:
                self._run_journal_loop()
            except Exception as exc:
                logger.exception(f"Erro no loop de leitura do journal: {exc}")

            if not self._stop_event.is_set():
                logger.warning("Leitura do journal interrompida. Tentando reiniciar em 3s.")
                self._stop_event.wait(timeout=3)

        self._terminate_process()
        logger.info("DspReader encerrado.")

    def _run_journal_loop(self) -> None:
        env = os.environ.copy()
        env.update({
            "SYSTEMD_COLORS": "0",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "PAGER": "cat",
        })

        with subprocess.Popen(
            JOURNAL_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        ) as proc:
            self._process = proc

            assert proc.stdout is not None

            for line in proc.stdout:
                if self._stop_event.is_set():
                    break

                if GREP_PATTERN not in line:
                    continue

                decoded = parse_journal_frame(line)
                if decoded:
                    logger.debug(
                        "Frame 04 64 decodificado: "
                        f"st=0x{decoded['charge_state']:02X} "
                        f"posix={decoded['posix']} "
                        f"T={decoded['t1_dsp']},{decoded['t2_board']},"
                        f"{decoded['t3_rack']},{decoded['t4_cable1']},"
                        f"{decoded['t5_cable2']}"
                    )
                    self._update_state(decoded)
                    self._detect_button_edges()
                else:
                    logger.warning(f"Linha 04 64 encontrada, mas não decodificada: {line!r}")

            stderr = ""
            if proc.stderr is not None:
                try:
                    stderr = proc.stderr.read().strip()
                except Exception:
                    stderr = ""
            if stderr:
                logger.warning(f"journalctl stderr: {stderr}")

            self._process = None

    def _terminate_process(self) -> None:
        proc = self._process
        if proc is None:
            return

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

        self._process = None

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _update_state(self, decoded: dict) -> None:
        """Atualiza DspState a partir do dict decodificado."""
        with self.state.lock:
            self.state.fn                 = decoded["fn"]
            self.state.sz                 = decoded["sz"]
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
            self.state.buttons_raw        = decoded["buttons_raw"]
            self.state.emergency          = decoded["emergency"]
            self.state.leakage_current    = decoded["leakage_current"]
            self.state.output_resistance  = decoded["output_resistance"]
            self.state.digital_raw        = decoded["digital_raw"]
            self.state.ax                 = decoded["ax"]
            self.state.ay                 = decoded["ay"]
            self.state.az                 = decoded["az"]
            self.state.dsp_timestamp      = decoded["dsp_timestamp"]
            self.state.eta                = decoded["eta"]
            self.state.raw_journal_line   = decoded.get("raw_journal_line", "")
            self.state.last_updated       = datetime.now()

    def _detect_button_edges(self) -> None:
        """
        Compara estado atual dos botões com o anterior.
        Publica ButtonEvent na fila para cada transição 0→1.

        Mapeamento físico validado no teste de fábrica:
          buttons_raw[0] = B1
          buttons_raw[1] = B2
          buttons_raw[2] = B3
          buttons_raw[3] = B4
        """
        with self.state.lock:
            current = self.state.buttons_raw

        for i, (prev, curr) in enumerate(zip(self._prev_buttons, current)):
            if prev == "0" and curr == "1":
                button_number = i + 1   # índice 0→B1, 3→B4
                event = ButtonEvent(button=button_number)
                self.event_queue.put(event)
                logger.debug(
                    f"ButtonEvent: B{button_number} pressionado "
                    f"(buttons_raw={current})"
                )

        self._prev_buttons = current
