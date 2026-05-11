"""
result.py

Estruturas de dados para acumular e consultar resultados do check.

Hierarquia:
  ItemResult   — resultado de um sub-item dentro de uma fase
  PhaseResult  — resultado consolidado de uma fase inteira
  CheckResult  — resultado global de todo o check
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


# ------------------------------------------------------------------ #
# Status possíveis                                                     #
# ------------------------------------------------------------------ #

class Status(Enum):
    RUNNING  = auto()   # em execução
    PASS     = auto()   # aprovado
    FAIL     = auto()   # reprovado
    SKIP     = auto()   # pulado pelo operador
    PENDING  = auto()   # ainda não executado


# ------------------------------------------------------------------ #
# Resultado de um sub-item                                            #
# ------------------------------------------------------------------ #

@dataclass
class ItemResult:
    name: str
    status: Status
    measured: str = ""       # valor medido, para log (ex: "T1=38°C")
    note: str = ""           # observação livre
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        parts = [f"[{self.status.name}] {self.name}"]
        if self.measured:
            parts.append(f"({self.measured})")
        if self.note:
            parts.append(f"— {self.note}")
        return " ".join(parts)


# ------------------------------------------------------------------ #
# Resultado de uma fase                                               #
# ------------------------------------------------------------------ #

@dataclass
class PhaseResult:
    phase_id: int
    phase_name: str
    items: list[ItemResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime = None

    def add(self, item: ItemResult):
        self.items.append(item)

    def finish(self):
        self.finished_at = datetime.now()

    @property
    def status(self) -> Status:
        """
        PASS   — todos os itens PASS ou SKIP
        FAIL   — pelo menos um item FAIL
        SKIP   — fase inteira pulada (nenhum item registrado, ou todos SKIP)
        PENDING— fase ainda não concluída
        """
        if self.finished_at is None:
            return Status.PENDING
        if not self.items:
            return Status.SKIP
        statuses = {item.status for item in self.items}
        if Status.FAIL in statuses:
            return Status.FAIL
        if statuses <= {Status.PASS, Status.SKIP}:
            return Status.PASS
        return Status.SKIP

    @property
    def passed(self) -> bool:
        return self.status == Status.PASS

    @property
    def failed(self) -> bool:
        return self.status == Status.FAIL

    def summary_lines(self) -> list[str]:
        lines = [f"=== Fase {self.phase_id}: {self.phase_name} [{self.status.name}] ==="]
        for item in self.items:
            lines.append(f"  {item}")
        if self.started_at and self.finished_at:
            duration = (self.finished_at - self.started_at).total_seconds()
            lines.append(f"  Duração: {duration:.1f}s")
        return lines


# ------------------------------------------------------------------ #
# Resultado global                                                     #
# ------------------------------------------------------------------ #

@dataclass
class CheckResult:
    serial_number: str = "N/A"
    phases: list[PhaseResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime = None

    def add_phase(self, phase: PhaseResult):
        self.phases.append(phase)

    def finish(self):
        self.finished_at = datetime.now()

    @property
    def overall_status(self) -> Status:
        """
        PASS  — todas as fases obrigatórias passaram
        FAIL  — pelo menos uma fase obrigatória falhou
        """
        if not self.phases:
            return Status.PENDING
        for phase in self.phases:
            if phase.failed:
                return Status.FAIL
        return Status.PASS

    @property
    def approved(self) -> bool:
        return self.overall_status == Status.PASS

    def to_log_text(self) -> str:
        """Gera o texto completo de log para salvar em disco."""
        lines = [
            "=" * 60,
            "FACTORY CHECK — LOG DE RESULTADO",
            f"Serial:  {self.serial_number}",
            f"Início:  {self.started_at.isoformat()}",
            f"Término: {self.finished_at.isoformat() if self.finished_at else 'em andamento'}",
            f"Resultado geral: {self.overall_status.name}",
            "=" * 60,
        ]
        for phase in self.phases:
            lines.extend(phase.summary_lines())
            lines.append("")
        return "\n".join(lines)
