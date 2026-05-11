# Factory Check — Documento de Referência

> Carregador Veicular — Modelo Simples (não simultâneo)  
> Versão consolidada das decisões de design e arquitetura  
> Gerado em: 2026-05-08

---

## 1. Contexto e Escopo

Software de verificação de montagem executado em linha de produção, antes do rack ser enviado a campo. Objetivo: confirmar que todos os subsistemas estão corretamente montados e funcionando, com registro de log para rastreabilidade.

**Fora do escopo desta versão:**
- Calibração de sensores
- Testes de isolação elétrica profunda
- Hardware de apoio externo além da maleta de testes

---

## 2. Decisões de Arquitetura

| Decisão | Resolução |
|---|---|
| Ativação do modo fábrica | Software separado, gravado via Clonezilla. Auto-inicia no boot via systemd. |
| Formatação do pendrive | Feita durante o processo Clonezilla, antes do check começar. |
| Número de série | Arquivo injetado no deploy: `/etc/factory/serial.conf` |
| Política de falha | Continuar sempre, exceto falha de comunicação DSP (interrompe tudo) |
| Log — camada 1 | Disco interno desde o boot (`/var/log/factory_check/`) |
| Log — camada 2 | Exportação para pendrive ao final, se disponível |
| Formato de log inicial | Texto com timestamp e sequência de eventos (MarkDown futuramente) |
| Display | Portrait 600×1024, sem toque |
| Input do operador | 4 pushbuttons físicos na base da tela |
| UI framework | Pygame |
| Python | 3.10.6 |
| Comunicação DSP | USB serial via FTDI — mesmo stream para telemetria e eventos de botão |

---

## 3. Mapeamento do Frame `04 64`

Frame enviado pelo DSP a cada **mínimo 5 segundos**, ou imediatamente ao ocorrer eventos (ex: botão pressionado). Formato: tokens separados por espaço. Frame real tem **35 tokens** (índice 0–34).

> ⚠️ O campo `|0|` (potência calculada) aparece em logs de pós-processamento mas **não existe no frame real**. O parser deve ignorá-lo.

```
04 64 11 00 001778255787 001 000 0.0 100 00000000 410 37459 0 38 30 24 28 29 000 0000 0 001 1000 00000 0000 94 2028 -88 2026-05-08T12:56:28.470 00 00 00 00 00 1
```

| Índice | Campo | Exemplo | Tipo | Uso no check |
|---|---|---|---|---|
| 0 | `fn` | `04` | hex fixo | Validar frame |
| 1 | `sz` | `64` | hex fixo | Validar frame |
| 2 | `st` | `11` | hex | Charge state — `0x32` aguardado p/ CCS, `0x81` p/ CHAdeMO |
| 3 | `cc` | `00` | int | Conector ativo — `00`=nenhum, `01`=CCS, `02`=CHAdeMO |
| 4 | `posix` | `001778255787` | int | Fase 1.1 — incremento confirma DSP vivo |
| 5 | `V` | `001` | float | Fase 8 — tensão instantânea veículo |
| 6 | `I` | `000` | float | Fase 8 — corrente fornecida |
| 7 | `Im` | `0.0` | float | Fase 8 — corrente solicitada pelo veículo |
| 8 | `e%` | `100` | int | Fase 8 — SOC do veículo |
| 9 | `et` | `00000000` | int | Fase 8 — duração da carga atual |
| 10 | `Vb` | `410` | uint | Fase 8 — tensão da bateria do veículo |
| 11 | `En` | `37459` | uint | Fase 8 — energia acumulada transferida |
| 12 | `Fan` | `0` | int | Fase 6 — `0`=desligado, `1`=ligado |
| 13 | `T1` | `38` | int | Fase 1.2 — temperatura do DSP |
| 14 | `T2` | `30` | int | Fase 1.3 — temperatura da placa DSP |
| 15 | `T3` | `24` | int | Fase 1.4 — temperatura interna do rack |
| 16 | `T4` | `28` | int | Fase 1.5 — temperatura cabo CCS 1 |
| 17 | `T5` | `29` | int | Fase 1.6 — temperatura cabo CCS 2 |
| 18 | `PB` | `000` | — | Ignorar (redundante com campo 19) |
| 19 | `4321` | `0000` | str(4 chars) | Fase 2 — botões individuais (`4321[3]`=B1 ... `4321[0]`=B4) |
| 20 | `em` | `0` | int | Fase 3 — botoeira de emergência |
| 21 | `Iil` | `001` | float | Reservado — corrente de fuga de entrada (calibração futura) |
| 22 | `Rno` | `1000` | int | Fase 8 — resistência normalizada de saída (`0`=sem carga, `1000`=em carga) |
| 23 | `F54321` | `00000` | — | Ignorar (não implementado no firmware) |
| 24 | `D4321` | `0000` | str(4 chars) | Fase 4 — `D4321[3]` (LSB) = sensor de porta |
| 25 | `Ax` | `94` | int | Fase 1.7 — acelerômetro X |
| 26 | `Ay` | `2028` | int | Fase 1.7 — acelerômetro Y |
| 27 | `Az` | `-88` | int | Fase 1.7 — acelerômetro Z |
| 28 | `timestamp` | `2026-05-08T12:56:28.470` | datetime | Log |
| 29–33 | `M1`–`M5` | `00 … 00` | — | Ignorar (temperaturas de módulos — não implementado) |
| 34 | `ETA` | `1` | — | Ignorar (tempo estimado de fim de carga) |

### Regras de parsing críticas

- **Validação de frame:** tokens 0 e 1 devem ser `04` e `64`. Frames inválidos são descartados.
- **Detecção de borda nos botões:** o parser compara `4321` com a leitura anterior e coloca um `ButtonEvent` na fila apenas na transição `0→1`. Evita processar o mesmo botão múltiplas vezes enquanto pressionado.
- **Sensor de porta:** `D4321[3]` (último caractere da string), `0`=fechada, `1`=aberta.
- **Acelerômetro:** falha se todos os três valores forem zero simultaneamente.
- **Temperaturas:** falha se valor `== 0` ou `>= 100`.

---

## 4. Fluxo de Fases

```
Boot automático (systemd)
    │
    ▼
Tela inicial — exibe número de série, aguarda 5s ou qualquer botão
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 1 — Testes automáticos (sem interação)         │
│  1.1  Comunicação DSP viva (posix incrementa)  ◄── falha aqui = STOP  │
│  1.2  T1 — temperatura DSP                          │
│  1.3  T2 — temperatura placa DSP                    │
│  1.4  T3 — temperatura interna rack                 │
│  1.5  T4 — temperatura cabo CCS 1                   │
│  1.6  T5 — temperatura cabo CCS 2                   │
│  1.7  Acelerômetro (Ax, Ay, Az não todos zero)      │
│  1.8  Conector = 00 (nenhum conectado)              │
│  1.9  Módulos de potência sem erro                  │
│  1.10 Pendrive presente e montável                  │
└─────────────────────────────────────────────────────┘
    │ resumo parcial na tela, avança após 5s
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 2 — Teste dos pushbuttons                      │
│  Um botão por vez, timeout 10s cada                 │
│  Timeout = FAIL registrado, avança automaticamente  │
│  ► A partir daqui botões disponíveis para interação │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 3 — Botoeira de emergência                     │
│  Passo 1: verificar liberada → lê `em`              │
│  Passo 2: operador pressiona → lê `em`              │
│  Passo 3: operador solta → lê `em`                  │
│  PASS se três estados mudaram conforme esperado     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 4 — Sensor de porta                            │
│  Passo 1: verificar fechada → lê D4321[3]           │
│  Passo 2: operador abre → lê D4321[3]               │
│  Passo 3: operador fecha → lê D4321[3]              │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 5 — Contatora (assistido)                      │
│  IPC → DSP: fechar contatora                        │
│  Operador confirma clique: B1=SIM / B2=NÃO          │
│  IPC → DSP: abrir contatora                         │
│  Operador confirma clique: B1=SIM / B2=NÃO          │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 6 — Ventilador (assistido)                     │
│  IPC → DSP: ligar ventilador                        │
│  Operador confirma rotação visual: B1=SIM / B2=NÃO  │
│  IPC → DSP: desligar ventilador                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 7 — Inspeções visuais                          │
│  Lista carregada de factory_inspections.yaml        │
│  Uma pergunta por tela: B1=PASS / B2=FAIL           │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 8 — Rede e testes de carga (condicional)       │
│  8.1  Ping 3.1.1.1    — link com Teltonika          │
│  8.2  Ping 8.8.8.8    — rota para internet          │
│  8.3  Ping 1.1.1.1    — redundância de rota         │
│  8.4  Ping google.com — resolução DNS               │
│  8.5  Ping cloudflare.com — redundância DNS         │
│  8a   Teste de carga CCS (opcional)                 │
│  8b   Teste de carga CHAdeMO (opcional)             │
│  Pular não gera FAIL — registrado como "não exec."  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ FASE 9 — Sumário e log                              │
│  Resultado consolidado por fase na tela             │
│  APROVADO somente se nenhum item obrigatório falhou │
│  Log exportado para pendrive se disponível          │
└─────────────────────────────────────────────────────┘
```

---

## 5. Layout de Botões (Fases 3 em diante)

| B1 | B2 | B3 | B4 |
|---|---|---|---|
| PASS ✓ / SIM | FALHA ✗ / NÃO | REPETIR ↺ | PULAR / PRÓXIMO → |

---

## 6. Testes de Carga — Detalhes

**Pré-condição:** rede disponível (ping 3.1.1.1 passou).

**CCS (Fase 8a):**
1. Instrução na tela para conectar maleta/veículo CCS
2. Sistema aguarda `cc == 01` e `st == 0x32` no frame (timeout configurável, ex: 60s)
3. Valida leituras de V, I, En durante carga
4. Operador encerra via B4

**CHAdeMO (Fase 8b):**
- Idem com `cc == 02` e `st == 0x81`

---

## 7. Arquivo de Inspeções Visuais

`factory_inspections.yaml` — editável pelo parceiro sem mexer no código:

```yaml
inspections:
  - "Cabo CCS fixado e trava encaixada corretamente?"
  - "Cabo CHAdeMO fixado e trava encaixada corretamente?"
  - "Conector CCS sem danos visíveis (pinos, vedação)?"
  - "Conector CHAdeMO sem danos visíveis?"
  - "Tampa traseira do rack fixada com todos os parafusos?"
  - "Display sem trincas ou danos visíveis?"
  - "Anel de LEDs íntegro e sem danos?"
  - "Botoeira de emergência sem danos físicos?"
  - "Ventilador sem obstrução visível?"
  - "Pendrive inserido no slot correto?"
```

---

## 8. Estrutura de Arquivos do Projeto

```
factory_check/
│
├── main.py                       # entry point
├── config.py                     # constantes: porta serial, resolução, timeouts, IPs
├── factory_inspections.yaml      # lista editável de inspeções
│
├── dsp/
│   ├── reader.py                 # thread de leitura serial, parser do frame
│   ├── state.py                  # DspState: dataclass com todos os campos
│   └── commands.py               # comandos ao DSP (contatora, ventilador)
│
├── phases/
│   ├── base.py                   # classe base Phase
│   ├── phase1_auto.py
│   ├── phase2_buttons.py
│   ├── phase3_emergency.py
│   ├── phase4_door.py
│   ├── phase5_contactor.py
│   ├── phase6_fan.py
│   ├── phase7_inspections.py
│   ├── phase8_network.py
│   ├── phase8b_load.py
│   └── phase9_summary.py
│
├── ui/
│   ├── renderer.py               # funções de desenho
│   └── theme.py                  # cores, fontes, layout 600x1024
│
├── logger.py                     # log dual: disco interno + pendrive
└── result.py                     # CheckResult: acumula resultados por fase
```

---

## 9. Modelo de Concorrência

```
┌─────────────────────┐    threading.Queue     ┌─────────────────────┐
│  Thread DSP Reader  │ ──── ButtonEvent ─────► │   Loop Pygame       │
│  (serial contínua)  │                         │   (render + input)  │
└─────────────────────┘                         └─────────────────────┘
         │               threading.Lock                  │
         └──────── DspState compartilhado ───────────────┘
```

- `DspState`: dataclass atualizada pela thread serial, lida pelo loop Pygame, protegida por `threading.Lock`
- `ButtonEvent`: colocado na fila apenas em transições `0→1` (detecção de borda)
- `queue.Queue`: thread-safe nativamente, sem necessidade de lock adicional

---

## 10. Interface Comum das Fases

```python
class Phase:
    def on_enter(self, state: DspState) -> None:
        """Chamado uma vez ao entrar na fase."""

    def update(self, state: DspState, events: list) -> PhaseResult:
        """Chamado a cada frame. Retorna RUNNING, PASS, FAIL ou SKIP."""

    def on_exit(self) -> CheckResult:
        """Retorna resultado consolidado da fase para o logger."""
```

`PhaseResult` e `CheckResult` definidos em `result.py`.

---

*Fim do documento de referência.*
