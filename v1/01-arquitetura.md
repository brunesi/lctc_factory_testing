# 01 — Arquitetura

## Visão geral do sistema

```
Boot automático (systemd)
    │
    ▼
main.py
    ├── DspReader (thread daemon)
    │     ├── Lê o journal do chargepoint.service continuamente
    │     ├── Filtra linhas contendo "04 64"
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
Thread DspReader                         Thread principal (Pygame)
──────────────────                       ──────────────────────────
journalctl -f                            drena event_queue
filtra linhas "04 64"                    phase.update(dsp_state, events)
parse_journal_frame() → DspState           └─ state.snapshot() usa state.lock
  └─ com state.lock                       renderer.render(screen, phase)
detecta borda botão                      pygame.display.flip()
  └─ event_queue.put(ButtonEvent)
```

- `DspState` protegido por `threading.Lock`
- `queue.Queue` é thread-safe nativamente
- `DspReader.send()` é placeholder temporário para comandos futuros

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

Frame publicado pelo `chargepoint.service` no journal, recuperado pelo comando:

```bash
journalctl -u chargepoint.service --since "30 seconds ago" -o cat -f | grep "04 64"
```

Exemplo de linha:

```text
04 64 11 00 001778496436 000 000   0.0 000 00000000 000 00000   0 20 12 07 11 12 000 0000  0 001 0000  00000  0000       80     2038      -56 2026-05-11T07:47:17.325 00 00 00 00 00 0
```

Ordem dos campos:

```text
fn sz st cc        posix   V   I Im    e%        et Vb     En Fan T1 T2 T3 T4 T5  PB 4321 em Iil Rno  F54321 D4321       Ax       Ay       Az timestamp               M1 M2 M3 M4 M5 ETA
```

| Índice | Campo | Tipo | Uso |
|---|---|---|---|
| 0 | fn | hex fixo `04` | validação |
| 1 | sz | hex fixo `64` | validação |
| 2 | st | hex | charge state |
| 3 | cc | int | conector: 0=nenhum 1=CCS 2=CHAdeMO |
| 4 | posix | int | heartbeat do DSP |
| 5 | V | int | tensão instantânea de carga |
| 6 | I | int | corrente instantânea de carga |
| 7 | Im | float | corrente solicitada pelo VE |
| 8 | e% | int | percentual de carga SOC |
| 9 | et | int | tempo decorrido de carga em segundos |
| 10 | Vb | int | tensão da bateria do VE |
| 11 | En | int | energia fornecida na carga atual |
| 12 | Fan | int | 0=off 1=on |
| 13–17 | T1–T5 | int | temperaturas °C |
| 18 | PB | — | ignorado |
| 19 | 4321 | str(4) | botões: `[0]=B4 … [3]=B1` |
| 20 | em | int | botoeira emergência 0=off 1=on |
| 21 | Iil | float | corrente de fuga |
| 22 | Rno | int | resistência normalizada saída |
| 23 | F54321 | — | status de módulos de potência, ignorado |
| 24 | D4321 | str(4) | sensores digitais: `[3]=porta` |
| 25–27 | Ax Ay Az | int | acelerômetro |
| 28 | timestamp | datetime | timestamp DSP |
| 29–33 | M1–M5 | — | temperaturas dos módulos de potência, não implementados, ignorados |
| 34 | eta | str | tempo para fim da carga |

## Protocolo de comandos ao DSP

Os métodos de comando ao DSP permanecem definidos como placeholders em `dsp/commands.py` e serão atualizados em etapa posterior.

| Comando | Status atual |
|---|---|
| Fechar contatora | placeholder |
| Abrir contatora | placeholder |
| fan_on / fan_off | placeholder |

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
_Última atualização: 2026-05-11_
