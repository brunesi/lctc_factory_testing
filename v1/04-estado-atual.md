# 04 — Estado Atual

_Última atualização: 2026-05-08_

## O que está funcionando

| Componente | Status |
|---|---|
| Boot e inicialização Pygame | ✓ funcionando |
| Abertura da porta serial | ✓ funcionando |
| DTR/RTS → nível 1 após abertura | ✓ fix aplicado |
| Recepção de frames binários do DSP | ✓ funcionando |
| Decodificação parcial do megapayload | ⚠ parcial — ver abaixo |
| Fase 1 — testes automáticos | ⚠ parcial — dados errados |
| Renderização da tela (Pygame) | ✓ funcionando |
| Tema visual 600×1024 | ✓ funcionando |

## Problema aberto — mapeamento do megapayload

`dsp/protocol.py::decode_megapayload()` tem mapeamento incorreto para campos após T3 (índice 25). Os campos afetados são T4, T5, acelerômetro X/Y/Z e Rno. Isso causa FAIL incorretos na Fase 1.

**Fonte de verdade:** `megapayload.docx` — tabela de 70 colunas com cada byte descrito.

**Ação para a próxima conversa:** reescrever `decode_megapayload()` byte a byte a partir do docx.

## Arquivos implementados

| Arquivo | Status |
|---|---|
| `config.py` | ✓ completo |
| `result.py` | ✓ completo |
| `logger.py` | ✓ completo |
| `dsp/state.py` | ✓ completo |
| `dsp/protocol.py` | ⚠ mapeamento parcialmente incorreto |
| `dsp/reader.py` | ✓ completo (binário, DTR/RTS fix incluído) |
| `dsp/commands.py` | ✓ parcial — fan_on/fan_off são TODO |
| `phases/base.py` | ✓ completo |
| `phases/phase1_auto.py` | ✓ completo |
| `phases/phase2_buttons.py` | ✓ completo |
| `phases/phase3_emergency.py` | ✓ completo |
| `phases/phase4_door.py` | ✓ completo |
| `phases/phase5_contactor.py` | ✓ completo |
| `phases/phase6_fan.py` | ✓ completo |
| `phases/phase7_inspections.py` | ✓ completo |
| `phases/phase8_network_load.py` | ✓ completo |
| `phases/phase9_summary.py` | ✓ completo |
| `ui/theme.py` | ✓ completo |
| `ui/renderer.py` | ✓ completo |
| `main.py` | ✓ completo |
| `factory_inspections.yaml` | ✓ lista inicial |

## Próximo passo imediato

Reescrever `decode_megapayload()` em `dsp/protocol.py` usando `megapayload.docx` como referência.
