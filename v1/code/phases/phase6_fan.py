"""
phases/phase6_fan.py

Fase 6 — Teste do ventilador.

Passo único assistido:
  IPC envia comando de acionamento ao DSP.
  Operador observa se o ventilador gira e confirma via botão.
  IPC envia comando de desligamento após confirmação.

  B1 = SIM / PASS  |  B2 = NÃO / FAIL  |  B3 = REPETIR comando

Nota: os comandos fan_on / fan_off estão marcados como TODO no
firmware do DSP (ventilador hoje é ativado por temperatura).
A fase está estruturada e pronta — quando o comando for
implementado no DSP, basta remover o TODO em dsp/commands.py.
Enquanto isso, o campo 'fan_status' do frame (0 ou 1) é exibido
na tela como informação auxiliar ao operador.
"""

import logging

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import DspReader, ButtonEvent
from dsp import commands
from result import PhaseResult, Status

logger = logging.getLogger(__name__)

INSTRUCTION = (
    "Comando de acionamento enviado ao ventilador.\n"
    "Observe se o ventilador está GIRANDO."
)
BUTTON_LEGEND = "[ B1: SIM / PASS ]   [ B2: NÃO / FAIL ]   [ B3: REPETIR ]"


class Phase6Fan(Phase):

    def __init__(self, reader: DspReader):
        super().__init__(phase_id=6, phase_name="Ventilador")
        self._reader = reader

        # Exposto ao renderer
        self.instruction: str = INSTRUCTION
        self.legend: str      = BUTTON_LEGEND
        self.fan_status: int  = 0    # valor atual do campo Fan no frame

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._send_fan_on()
        logger.info("Fase 6 iniciada — comando fan_on enviado.")

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        snap = state.snapshot()
        self.fan_status = snap.fan_status   # atualiza indicador na tela

        if self._button_pressed(events, 1):     # SIM
            self._pass(
                "Ventilador girando",
                measured=f"confirmado pelo operador (fan_status={snap.fan_status})",
            )
            self._send_fan_off()
            return Status.PASS

        if self._button_pressed(events, 2):     # NÃO
            self._fail(
                "Ventilador girando",
                measured=f"não confirmado pelo operador (fan_status={snap.fan_status})",
                note="Verificar ventilador, cabeamento e comando DSP (TODO)",
            )
            self._send_fan_off()
            return Status.FAIL

        if self._button_pressed(events, 3):     # REPETIR
            logger.info("Fase 6: repetindo comando fan_on.")
            self._send_fan_on()

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _send_fan_on(self) -> None:
        ok = commands.fan_on(self._reader)
        if not ok:
            logger.warning(
                "Fase 6: fan_on retornou False (comando não implementado no DSP)."
            )

    def _send_fan_off(self) -> None:
        ok = commands.fan_off(self._reader)
        if not ok:
            logger.warning(
                "Fase 6: fan_off retornou False (comando não implementado no DSP)."
            )
