# 01 — Arquitetura

## Visão geral do sistema

```
Boot automático (systemd)
    │
    ▼
main.py
    ├── DspReader (thread daemon)
    │     ├── Lê serial continuamente
    │     ├── Atualiza DspState (com Lock)
    │     └── Detecta bordas nos botões → ButtonEvent na Queue
    │
    ├── Loop Pygame (thread principal)
    │     ├── Drena Queue de ButtonEvents
    │     ├── Chama phase.update(state, events)
    │     ├── Chama renderer.render(screen, phase)
    │     └── Gerencia transições de fase
    │
    └── CheckResult (acumula resultados de todas as fases)
```

## Modelo de concorrência

```
Thread DspReader                    Thread principal (Pygame)
──────────────────                  ──────────────────────────
readline() da serial                drena event_queue
parse_frame() → DspState            phase.update(dsp_state, events)
  └─ com state.lock                   └─ state.snapshot() usa state.lock
detecta borda botão                 renderer.render(screen, phase)
  └─ event_queue.put(ButtonEvent)   pygame.display.flip()
```

- `DspState` protegido por `threading.Lock`
- `queue.Queue` é thread-safe nativamente
- `DspReader.send()` protegido por `_write_lock` para escritas concorrentes

## Estrutura de arquivos

```
factory_check/
├── main.py                       # entry point, loop principal
├── config.py                     # todas as constantes
├── factory_inspections.yaml      # lista de inspeções visuais (editável)
├── result.py                     # ItemResult, PhaseResult, CheckResult
├── logger.py                     # log dual disco+pendrive
│
├── dsp/
│   ├── state.py                  # DspState: dataclass com campos do frame
│   ├── reader.py                 # DspReader thread + parser + ButtonEvent
│   └── commands.py               # contactor_close/open, fan_on/off
│
├── phases/
│   ├── base.py                   # classe abstrata Phase
│   ├── phase1_auto.py            # testes automáticos
│   ├── phase2_buttons.py         # teste dos pushbuttons
│   ├── phase3_emergency.py       # botoeira de emergência
│   ├── phase4_door.py            # sensor de porta
│   ├── phase5_contactor.py       # contatora
│   ├── phase6_fan.py             # ventilador
│   ├── phase7_inspections.py     # inspeções visuais (lê YAML)
│   ├── phase8_network_load.py    # rede + testes de carga
│   └── phase9_summary.py         # sumário final + log
│
└── ui/
    ├── theme.py                  # cores, fontes, layout 600×1024
    └── renderer.py               # renderizadores por fase
```

## Interface das fases

Todas as fases implementam a mesma interface:

```python
class Phase(ABC):
    def on_enter(self, state: DspState) -> None: ...
    def update(self, state: DspState, events: list[ButtonEvent]) -> Status: ...
    def on_exit(self) -> PhaseResult: ...
```

O loop principal em `main.py` trata todas as fases de forma uniforme.

## Frame DSP `04 64`

Frame enviado pelo DSP a cada mínimo 5s (imediatamente em eventos).
35 tokens separados por espaço.

| Índice | Campo | Tipo | Uso |
|---|---|---|---|
| 0 | fn | hex fixo `04` | validação |
| 1 | sz | hex fixo `64` | validação |
| 2 | st | hex | charge state |
| 3 | cc | int | conector: 0=nenhum 1=CCS 2=CHAdeMO |
| 4 | posix | int | heartbeat do DSP |
| 5–11 | V I Im e% et Vb En | float/uint | variáveis de carga |
| 12 | Fan | int | 0=off 1=on |
| 13–17 | T1–T5 | int | temperaturas °C |
| 18 | PB | — | ignorado |
| 19 | 4321 | str(4) | botões: `[0]=B4 … [3]=B1` |
| 20 | em | int | botoeira emergência |
| 21 | Iil | float | corrente de fuga (reservado) |
| 22 | Rno | int | resistência normalizada saída |
| 23 | F54321 | — | ignorado |
| 24 | D4321 | str(4) | sensores digitais: `[3]=porta` |
| 25–27 | Ax Ay Az | int | acelerômetro |
| 28 | timestamp | datetime | timestamp DSP |
| 29–34 | M1–M5 ETA | — | ignorados |

## Protocolo de comandos ao DSP

```
SOP(0x7e) | function | size_msb | size_lsb | data | checksum | EOP(0x7d)
checksum = complemento de 2 de 8 bits sobre [function, size_msb, size_lsb, data]
```

| Comando | function | data |
|---|---|---|
| Fechar contatora | 0x0C | `[0x01]` |
| Abrir contatora | 0x0C | `[0x02]` |
| fan_on / fan_off | TODO | TODO |

## Layout de tela (600×1024)

```
┌──────────────────────────────┐  y=0
│  HEADER (72px)               │  nome da fase
├──────────────────────────────┤  y=72
│  BAR (8px)                   │  countdown / progresso
├──────────────────────────────┤  y=80
│                              │
│  CONTENT (variável)          │  conteúdo principal da fase
│                              │
├──────────────────────────────┤  y=944
│  FOOTER (80px)               │  legenda dos botões
└──────────────────────────────┘  y=1024
```

## Layout de botões (Fase 3 em diante)

| B1 | B2 | B3 | B4 |
|---|---|---|---|
| PASS ✓ / SIM | FAIL ✗ / NÃO | REPETIR ↺ | PULAR / PRÓXIMO → |

---
_Última atualização: 2026-05-08_
