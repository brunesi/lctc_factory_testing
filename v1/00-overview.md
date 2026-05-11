# 00 — Visão Geral

## Objetivo

Software de verificação de montagem executado em linha de produção, antes do rack de carregador veicular ser enviado a campo. Confirma que todos os subsistemas estão corretamente montados e funcionando, com registro de log para rastreabilidade.

## Produto

**Carregador Veicular — Modelo Simples (não simultâneo)**
- Um único DSP, um único conector (CCS + CHAdeMO)
- Display portrait 600×1024, sem toque
- Quatro pushbuttons físicos na base da tela
- Conectividade Ethernet (modem Teltonika) e 4G

## Stack

| Camada | Tecnologia |
|---|---|
| Hardware IPC | LattePanda v1 |
| SO | Ubuntu 16.04 |
| Linguagem | Python 3.10.6 |
| UI | Pygame |
| Comunicação DSP | USB serial via FTDI (`/dev/ftdiA`) |
| Protocolo DSP | Proprietário — frames binários com checksum complemento de 2 |
| Telemetria DSP | Frame `04 64` em texto, separado por espaços, mínimo a cada 5s |
| Log | Disco interno (`/var/log/factory_check/`) + pendrive (`/media/pendrive/`) |
| Config inspeções | YAML (`factory_inspections.yaml`) |

## Dependências Python

```bash
pip3 install pygame pyserial pyyaml
```

## Status

Implementação inicial completa — pronto para testes em hardware.

## Execução

```bash
python3 main.py
```

Para desenvolvimento sem tela cheia:
```python
# config.py
FULLSCREEN = False
```

---
_Última atualização: 2026-05-08_
