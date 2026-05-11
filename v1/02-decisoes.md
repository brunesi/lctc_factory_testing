# 02 — Log de Decisões

Registro das principais decisões de design com justificativa.

---

## D01 — Software separado para modo fábrica

**Decisão:** O factory check é um software independente, gravado via Clonezilla. Não é um modo do software de produção.

**Alternativas consideradas:**
- Ativação por cartão RFID: descartado — o leitor RFID pode estar com falha, e não foi testado
- Sequência de botões: descartado — depende dos botões e do DSP estarem funcionando, exatamente o que ainda não sabemos
- Arquivo flag: viável, mas menos limpo que softwares separados

**Justificativa:** Qualquer mecanismo de ativação baseado em hardware pressupõe que esse hardware funciona. Software separado elimina esse problema completamente e alinha com o processo existente de deploy via Clonezilla. Ao gravar a imagem, o operador confirma implicitamente que a LattePanda está operando.

---

## D02 — Pygame como framework de UI

**Decisão:** Pygame para renderização e loop de eventos.

**Alternativas consideradas:**
- Tkinter: familiar para o desenvolvedor, mas luta contra o modelo de widgets para uma tela kiosk sem formulários
- PyQt5: mais pesado, possível atrito com Ubuntu 16.04

**Justificativa:** Pygame oferece controle total da superfície de renderização. O loop de eventos se encaixa naturalmente no modelo "aguardo botão, atualizo tela, avanço fase". Para uma tela que na prática não usa nenhum widget de formulário, é a escolha mais simples.

---

## D03 — Thread serial com DspState compartilhado

**Decisão:** DspReader roda em thread daemon, atualiza DspState protegido por Lock. Botões detectados por borda publicam ButtonEvent em Queue.

**Alternativas consideradas:**
- asyncio: o restante do projeto já usa asyncio; dificultaria integrar com Pygame que tem seu próprio loop síncrono
- Polling síncrono da serial: bloquearia o loop de renderização

**Justificativa:** DSP envia frames a cada ~5s (ou imediatamente em eventos). Pygame precisa de loop responsivo a 30fps. Os dois ritmos precisam coexistir sem bloqueio.

---

## D04 — Detecção de borda nos botões

**Decisão:** A thread serial detecta transições `0→1` no campo `4321` do frame e publica um `ButtonEvent` na fila. O loop principal nunca lê o estado raw dos botões diretamente.

**Justificativa:** Sem detecção de borda, um botão pressionado por 200ms seria processado em ~6 frames a 30fps, causando múltiplas ações. A fila garante exatamente um evento por pressionamento.

---

## D05 — Política de falha: continuar sempre

**Decisão:** Com exceção da falha de comunicação DSP (Fase 1.1), todos os itens que falham são registrados e a execução continua.

**Alternativas consideradas:**
- Parar em qualquer falha: impede verificar os demais subsistemas

**Justificativa:** O parceiro precisa de um relatório completo de todos os problemas de montagem em uma única passagem. Parar na primeira falha obrigaria múltiplas execuções.

**Exceção:** Falha na comunicação DSP (Fase 1.1) interrompe tudo porque todas as outras verificações dependem do DSP.

---

## D06 — Número de série via arquivo de configuração

**Decisão:** `/etc/factory/serial.conf` — arquivo injetado no momento do deploy Clonezilla.

**Alternativas consideradas:**
- Entrada manual por botões: trabalhoso e sujeito a erro
- DIP switches / straps de hardware: não existem no hardware atual
- Ignorar: log sem serial, associação por timestamp

**Justificativa:** A Opção C (arquivo injetado) é a que melhor equilibra rastreabilidade e simplicidade operacional. O processo de deploy já tem associação rack↔serial; basta persistir essa informação no arquivo.

---

## D07 — Log em duas camadas

**Decisão:** Log interno em `/var/log/factory_check/` desde o boot. Exportação para pendrive ao final, se disponível.

**Justificativa:** O pendrive é ele próprio objeto de teste (Fase 1.10). Não é possível depender dele como única camada de log. O disco interno garante que nenhum resultado se perde mesmo se o pendrive falhar.

---

## D08 — Pings em cascata com diagnóstico por camada

**Decisão:** 5 pings em sequência: Teltonika → 8.8.8.8 → 1.1.1.1 → google.com → cloudflare.com. Se o primeiro falhar, os demais são registrados como SKIP.

**Justificativa:** Cada ping testa uma camada diferente da pilha de rede. Registrar todos como FAIL quando o problema real é um único cabo Ethernet seria enganoso para o operador. A cascata aponta exatamente onde a cadeia quebrou.

---

## D09 — Testes de carga são condicionais (SKIP ≠ FAIL)

**Decisão:** Testes CCS e CHAdeMO na Fase 8 são opcionais. Não executados ficam ausentes no log, sem FAIL.

**Justificativa:** O parceiro pode não ter maleta de testes ou veículo disponível na linha de produção inicial. O resultado geral do check não deve ser comprometido por equipamento externo ausente — isso é uma limitação operacional, não um defeito do rack.

---

## D10 — fan_on / fan_off como TODO

**Decisão:** Comandos de ventilador estruturados no código mas retornando False com warning no log.

**Justificativa:** O ventilador hoje é ativado por temperatura pelo próprio DSP. O protocolo de comando para controle manual não foi implementado no firmware. A fase 6 está estruturada e pronta — quando o comando for implementado no DSP, basta preencher os payloads em `dsp/commands.py`.

---
_Última atualização: 2026-05-08_
