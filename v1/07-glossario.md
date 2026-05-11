# 07 — Glossário

Termos do domínio e do projeto.

---

## Hardware

**LattePanda v1**
Computador industrial de placa única (SBC) usado como IPC (unidade de processamento principal) do carregador. Roda Ubuntu 16.04.

**DSP**
Controlador de potência dedicado. No modelo simples, há um único DSP controlando o conector. Comunica com a LattePanda via USB serial (FTDI FT4232H).

**FTDI FT4232H**
Conversor USB-Serial usado para comunicação entre LattePanda e DSP. Mapeia portas via udev (`/dev/ftdiA`, `/dev/ftdiD`, etc.).

**Módulos de potência**
Componentes responsáveis pela entrega de energia ao veículo. Monitorados pelo DSP. Possuem displays físicos próprios que podem exibir códigos de falha.

**Contatora**
Relé de alta potência que conecta/desconecta os módulos de potência ao conector de carga. Acionada por comando do IPC via DSP. Não tem feedback de estado no frame de telemetria — confirmação é auditiva (clique).

**Botoeira de emergência**
Botão de parada de emergência com trava mecânica. Estado monitorado pelo DSP (campo `em` no frame). `0` = liberada, `1` = pressionada/travada.

**Teltonika**
Modem 4G/LTE usado para conectividade remota do carregador. IP fixo `3.1.1.1`. A LattePanda tem IP fixo `3.1.1.2` atribuído pelo Teltonika.

**Maleta de testes**
Equipamento externo que simula um veículo elétrico para fins de teste de carga. Permite testar CCS e CHAdeMO sem um veículo real. O parceiro não possui atualmente — pode ser adquirida.

---

## Protocolos de carga

**CCS (Combined Charging System)**
Padrão de carregamento DC de alta potência. Conector tipo 2 com pinos DC adicionais. `cc=1` no frame DSP quando conectado. Estado de plugue detectado: `st=0x32`.

**CHAdeMO**
Padrão de carregamento DC japonês. `cc=2` no frame DSP quando conectado. Estado de plugue detectado: `st=0x81`.

**OCPP (Open Charge Point Protocol)**
Protocolo de comunicação entre o carregador e o backend via WebSocket. Não é relevante para o factory check, mas é o protocolo do software de produção.

---

## Frame DSP

**Frame `04 64`**
Frame de telemetria enviado pelo DSP. `04` = function code, `64` = size (hex). Contém estado completo do carregador em texto separado por espaços.

**posix**
Campo do frame que contém um contador interno do DSP. Incrementa a cada envio. Usado para verificar que o DSP está vivo — não é Unix timestamp.

**charge_state (st)**
Estado atual do processo de carga. Valores relevantes para o check: `0x32` = plugue CCS detectado, `0x81` = plugue CHAdeMO detectado.

**Rno**
Resistência normalizada de saída. `0` = sem carga, `1000` = em carga com isolação ok. Valores entre 1 e 999 em carga indicam problema de isolação.

**T1–T5**
Temperaturas: T1=DSP, T2=placa DSP, T3=interna rack, T4=cabo CCS 1, T5=cabo CCS 2. Critério de check: `0 < T < 100°C`.

**Iil**
Corrente de fuga de entrada. Reservado para uso futuro no processo de calibração.

---

## Software do factory check

**ButtonEvent**
Dataclass publicada na `queue.Queue` pelo `DspReader` quando detecta transição `0→1` em um botão. Contém o número do botão (1–4) e timestamp.

**DspState**
Dataclass com todos os campos do frame `04 64`. Atualizada pela thread `DspReader` sob `threading.Lock`. Lida pelo loop principal via `snapshot()`.

**Phase**
Classe base abstrata. Toda fase implementa `on_enter`, `update` e `on_exit`. O loop principal trata todas as fases de forma uniforme.

**PhaseResult / CheckResult**
Estruturas de acumulação de resultados. `PhaseResult` agrega `ItemResult`s de uma fase. `CheckResult` agrega todos os `PhaseResult`s do check completo.

**Status**
Enum: `RUNNING`, `PASS`, `FAIL`, `SKIP`, `PENDING`. Retornado por `phase.update()` para sinalizar o estado atual da fase.

**snapshot()**
Método de `DspState` que retorna uma cópia thread-safe do estado atual. Deve ser usado dentro de `phase.update()` ao invés de ler campos diretamente.

---

## Siglas

| Sigla | Significado |
|---|---|
| IPC | Industrial PC (LattePanda) |
| DSP | Digital Signal Processor (controlador de potência) |
| CCS | Combined Charging System |
| SOC | State of Charge (estado de carga da bateria do veículo) |
| SBC | Single Board Computer |
| FTDI | Future Technology Devices International (fabricante do conversor USB-Serial) |
| OCPP | Open Charge Point Protocol |
| EV | Electric Vehicle |

---
_Última atualização: 2026-05-08_
