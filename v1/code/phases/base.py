"""
phases/base.py

Classe base para todas as fases do factory check.

Contrato:
  on_enter(state)         — chamado uma vez ao entrar na fase
  update(state, events)   — chamado a cada frame; retorna Status
  on_exit()               — retorna PhaseResult consolidado

O loop principal em main.py trata todas as fases de forma uniforme
através dessa interface.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime

from dsp.state import DspState
from dsp.reader import ButtonEvent
from result import PhaseResult, ItemResult, Status

logger = logging.getLogger(__name__)


class Phase(ABC):
    """
    Classe base abstrata para todas as fases.

    Subclasses devem implementar on_enter, update e on_exit.
    Métodos auxiliares (_pass, _fail, _skip) facilitam
    o registro de itens sem repetição de código.
    """

    def __init__(self, phase_id: int, phase_name: str):
        self.phase_id = phase_id
        self.phase_name = phase_name
        self._result = PhaseResult(phase_id=phase_id, phase_name=phase_name)
        self._status = Status.RUNNING

    # ---------------------------------------------------------------- #
    # Interface pública — implementada pelas subclasses                 #
    # ---------------------------------------------------------------- #

    @abstractmethod
    def on_enter(self, state: DspState) -> None:
        """
        Chamado uma vez quando a fase se torna ativa.
        Usar para inicializar estado interno, registrar timestamp,
        enviar comandos iniciais ao DSP se necessário.
        """

    @abstractmethod
    def update(self, state: DspState, events: list[ButtonEvent]) -> Status:
        """
        Chamado a cada frame do loop Pygame.
        Deve retornar:
          Status.RUNNING  — fase ainda em andamento
          Status.PASS     — fase concluída com aprovação
          Status.FAIL     — fase concluída com falha
          Status.SKIP     — fase pulada pelo operador
        """

    @abstractmethod
    def on_exit(self) -> PhaseResult:
        """
        Chamado quando update retorna algo diferente de RUNNING.
        Deve finalizar o PhaseResult e retorná-lo.
        """

    # ---------------------------------------------------------------- #
    # Helpers para subclasses                                           #
    # ---------------------------------------------------------------- #

    def _record(
        self,
        name: str,
        status: Status,
        measured: str = "",
        note: str = "",
    ) -> ItemResult:
        """Cria um ItemResult, registra no PhaseResult e faz log."""
        item = ItemResult(name=name, status=status, measured=measured, note=note)
        self._result.add(item)
        logger.info(str(item))
        return item

    def _pass(self, name: str, measured: str = "", note: str = "") -> ItemResult:
        return self._record(name, Status.PASS, measured, note)

    def _fail(self, name: str, measured: str = "", note: str = "") -> ItemResult:
        return self._record(name, Status.FAIL, measured, note)

    def _skip(self, name: str, note: str = "") -> ItemResult:
        return self._record(name, Status.SKIP, note=note)

    def _finish(self, status: Status) -> PhaseResult:
        """Finaliza o PhaseResult e atualiza _status."""
        self._status = status
        self._result.finish()
        logger.info(
            f"Fase {self.phase_id} '{self.phase_name}' encerrada: {status.name}"
        )
        return self._result

    def _button_pressed(self, events: list[ButtonEvent], button: int) -> bool:
        """Verifica se um botão específico foi pressionado neste frame."""
        return any(e.button == button for e in events)

    def _any_button_pressed(self, events: list[ButtonEvent]) -> bool:
        """Verifica se qualquer botão foi pressionado neste frame."""
        return len(events) > 0

    @property
    def name(self) -> str:
        return self.phase_name
