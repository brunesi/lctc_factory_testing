"""
phases/phase2_buttons.py

Fase 2 — Teste dos pushbuttons.

Testa cada botão individualmente em sequência (B1 → B4).
Para cada botão:
  - Exibe instrução clara na tela
  - Aguarda o botão ser pressionado (detectado via ButtonEvent)
  - Se pressionado dentro do timeout → PASS
  - Se timeout esgotar → FAIL registrado, avança automaticamente

A partir da conclusão desta fase os botões estão formalmente
testados e disponíveis para interação nas fases seguintes.

Layout de botões (ativo a partir da Fase 3):
  B1=PASS  B2=FAIL  B3=REPETIR  B4=PULAR
"""

import logging
import time

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, Status
import config

logger = logging.getLogger(__name__)

# Descrições físicas dos botões para instrução ao operador
BUTTON_LABELS = {
    1: "BOTÃO 1  (primeiro da esquerda)",
    2: "BOTÃO 2  (segundo da esquerda)",
    3: "BOTÃO 3  (terceiro da esquerda)",
    4: "BOTÃO 4  (quarto da esquerda / direita)",
}


class Phase2Buttons(Phase):

    def __init__(self):
        super().__init__(phase_id=2, phase_name="Teste dos Pushbuttons")

        self._buttons_to_test = [1, 2, 3, 4]
        self._current_index   = 0          # índice em _buttons_to_test
        self._button_start    = 0.0        # monotonic do início do teste atual

        # Exposto ao renderer
        self.current_button: int  = 1      # botão sendo testado agora
        self.countdown: float     = 0.0    # segundos restantes

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        self._current_index  = 0
        self._button_start   = time.monotonic()
        self.current_button  = self._buttons_to_test[0]
        self.countdown       = float(config.TIMEOUT_BUTTON_TEST)
        logger.info("Fase 2 iniciada — teste dos pushbuttons.")

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        current_btn = self._buttons_to_test[self._current_index]
        elapsed     = time.monotonic() - self._button_start
        remaining   = config.TIMEOUT_BUTTON_TEST - elapsed

        self.current_button = current_btn
        self.countdown      = max(0.0, remaining)

        # Verifica se o botão correto foi pressionado
        if self._button_pressed(events, current_btn):
            self._pass(
                f"Botão {current_btn}",
                measured=f"pressionado em {elapsed:.1f}s",
            )
            return self._advance()

        # Timeout — registra falha e avança
        if remaining <= 0:
            self._fail(
                f"Botão {current_btn}",
                measured=f"sem resposta após {config.TIMEOUT_BUTTON_TEST}s",
                note="Verificar conexão do pushbutton ao DSP",
            )
            return self._advance()

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        # PASS somente se todos os 4 botões passaram
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _advance(self) -> Status:
        """
        Avança para o próximo botão.
        Se todos foram testados, encerra a fase.
        """
        self._current_index += 1

        if self._current_index >= len(self._buttons_to_test):
            # Todos testados — deixa on_exit determinar PASS/FAIL
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        # Prepara próximo botão
        self._button_start  = time.monotonic()
        self.current_button = self._buttons_to_test[self._current_index]
        self.countdown      = float(config.TIMEOUT_BUTTON_TEST)
        logger.info(f"Avançando para botão {self.current_button}")
        return Status.RUNNING
