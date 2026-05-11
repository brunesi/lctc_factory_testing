"""
phases/phase3_emergency.py

Fase 3 — Teste da botoeira de emergência.

Três passos sequenciais, cada um com timeout individual:

  Passo 1 — VERIFY_RELEASED
    Sistema lê campo 'em' do frame.
    Aguarda em=0 (botoeira liberada).
    Se já está liberada: PASS imediato, avança.
    Se timeout: FAIL, avança (política: continuar sempre).

  Passo 2 — WAIT_PRESSED
    Instrução: "Pressione a botoeira de emergência."
    Aguarda em=1 (botoeira pressionada).
    Detecção por transição de estado no frame DSP.

  Passo 3 — WAIT_RELEASED
    Instrução: "Gire e solte a botoeira."
    Aguarda em=0 (botoeira liberada novamente).

Resultado: PASS somente se os três passos passaram.
"""

import logging
import time
from enum import Enum, auto

from phases.base import Phase
from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, Status
import config

logger = logging.getLogger(__name__)


class _Step(Enum):
    VERIFY_RELEASED = auto()   # Passo 1: confirmar liberada
    WAIT_PRESSED    = auto()   # Passo 2: aguardar pressionada
    WAIT_RELEASED   = auto()   # Passo 3: aguardar solta novamente


# Textos de instrução para cada passo
STEP_INSTRUCTIONS = {
    _Step.VERIFY_RELEASED: (
        "Passo 1 de 3",
        "Verifique que a botoeira de emergência\nestá LIBERADA (puxada para fora).",
        "Aguardando confirmação...",
    ),
    _Step.WAIT_PRESSED: (
        "Passo 2 de 3",
        "PRESSIONE a botoeira de emergência\n(empurre até travar).",
        "Aguardando acionamento...",
    ),
    _Step.WAIT_RELEASED: (
        "Passo 3 de 3",
        "GIRE e SOLTE a botoeira de emergência\n(gire no sentido indicado para liberar).",
        "Aguardando liberação...",
    ),
}


class Phase3Emergency(Phase):

    def __init__(self):
        super().__init__(phase_id=3, phase_name="Botoeira de Emergência")

        self._step         = _Step.VERIFY_RELEASED
        self._step_start   = 0.0
        self._prev_em      = -1          # estado anterior de 'em', -1 = não lido ainda

        # Exposto ao renderer
        self.step_label: str       = ""
        self.instruction: str      = ""
        self.sub_instruction: str  = ""
        self.countdown: float      = 0.0
        self.em_state: int         = 0   # último valor lido de 'em'

    # ---------------------------------------------------------------- #
    # Interface Phase                                                   #
    # ---------------------------------------------------------------- #

    def on_enter(self, state: DspState) -> None:
        snap = state.snapshot()
        self._prev_em    = snap.emergency
        self._step_start = time.monotonic()
        self._update_display(_Step.VERIFY_RELEASED)
        logger.info(
            f"Fase 3 iniciada. estado inicial da botoeira: em={snap.emergency}"
        )

    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        snap = state.snapshot()
        self.em_state = snap.emergency
        self.countdown = max(
            0.0,
            config.TIMEOUT_EMERGENCY_STEP - (time.monotonic() - self._step_start)
        )

        match self._step:

            case _Step.VERIFY_RELEASED:
                return self._handle_verify_released(snap)

            case _Step.WAIT_PRESSED:
                return self._handle_wait_pressed(snap)

            case _Step.WAIT_RELEASED:
                return self._handle_wait_released(snap)

        return Status.RUNNING

    def on_exit(self) -> PhaseResult:
        has_fail = any(
            item.status == Status.FAIL
            for item in self._result.items
        )
        return self._finish(Status.FAIL if has_fail else Status.PASS)

    # ---------------------------------------------------------------- #
    # Handlers por passo                                               #
    # ---------------------------------------------------------------- #

    def _handle_verify_released(self, snap: DspState) -> Status:
        if snap.emergency == 0:
            self._pass(
                "Passo 1: botoeira liberada",
                measured="em=0",
            )
            return self._go_to(_Step.WAIT_PRESSED)

        if self._timed_out():
            self._fail(
                "Passo 1: botoeira liberada",
                measured=f"em={snap.emergency}",
                note="Botoeira permaneceu pressionada — libere antes de continuar",
            )
            return self._go_to(_Step.WAIT_PRESSED)

        return Status.RUNNING

    def _handle_wait_pressed(self, snap: DspState) -> Status:
        # Detecta transição 0→1
        if self._prev_em == 0 and snap.emergency == 1:
            self._pass(
                "Passo 2: botoeira pressionada",
                measured="em=0→1",
            )
            self._prev_em = snap.emergency
            return self._go_to(_Step.WAIT_RELEASED)

        if self._timed_out():
            self._fail(
                "Passo 2: botoeira pressionada",
                measured=f"em={snap.emergency} (sem transição após {config.TIMEOUT_EMERGENCY_STEP}s)",
                note="Pressione a botoeira de emergência",
            )
            self._prev_em = snap.emergency
            return self._go_to(_Step.WAIT_RELEASED)

        self._prev_em = snap.emergency
        return Status.RUNNING

    def _handle_wait_released(self, snap: DspState) -> Status:
        # Detecta transição 1→0
        if self._prev_em == 1 and snap.emergency == 0:
            self._pass(
                "Passo 3: botoeira liberada novamente",
                measured="em=1→0",
            )
            self._prev_em = snap.emergency
            # Fase concluída — resultado em on_exit
            has_fail = any(
                item.status == Status.FAIL
                for item in self._result.items
            )
            return Status.FAIL if has_fail else Status.PASS

        if self._timed_out():
            self._fail(
                "Passo 3: botoeira liberada novamente",
                measured=f"em={snap.emergency} (sem transição após {config.TIMEOUT_EMERGENCY_STEP}s)",
                note="Gire e solte a botoeira de emergência",
            )
            self._prev_em = snap.emergency
            return Status.FAIL

        self._prev_em = snap.emergency
        return Status.RUNNING

    # ---------------------------------------------------------------- #
    # Helpers internos                                                  #
    # ---------------------------------------------------------------- #

    def _timed_out(self) -> bool:
        return (time.monotonic() - self._step_start) >= config.TIMEOUT_EMERGENCY_STEP

    def _go_to(self, step: _Step) -> Status:
        """Transita para o próximo passo e reinicia o timer."""
        self._step       = step
        self._step_start = time.monotonic()
        self._update_display(step)
        logger.info(f"Fase 3: avançando para {step.name}")
        return Status.RUNNING

    def _update_display(self, step: _Step) -> None:
        label, instruction, sub = STEP_INSTRUCTIONS[step]
        self.step_label      = label
        self.instruction     = instruction
        self.sub_instruction = sub
        self.countdown       = float(config.TIMEOUT_EMERGENCY_STEP)
