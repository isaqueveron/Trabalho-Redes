# Protocolo de Enlace com Transferência de Imagem via UDP

Implementação de um protocolo de enlace industrial adaptado para transferência confiável de arquivos sobre UDP, incluindo detecção de erros por checksum duplo, byte stuffing conforme especificação do protocolo original, retransmissão automática (ARQ Stop-and-Wait) e RTT dinâmico com filtro de Karn.

> **Origem do protocolo:** `protocolo_enlace.py` é uma adaptação direta de um driver industrial real. O formato do telegrama, os checksums e as regras de byte stuffing seguem a especificação original desse driver.

---

## Estrutura dos Arquivos

```
.
├── protocolo_enlace.py     # Núcleo do protocolo: criação e validação de telegramas
├── transmissor.py          # Lado cliente: lê o arquivo e o envia em blocos
├── receptor.py             # Lado servidor: recebe os blocos e reconstrói o arquivo
└── modelos_medios_dmc.png  # Arquivo de entrada (deve ser fornecido pelo usuário)
```

---

## Como Funciona

### Formato do Telegrama

Cada mensagem trocada entre transmissor e receptor segue o formato abaixo:

```
[STX] [COMMAND] [RX] [TX] [N_PARAMS] [PARAM_0 ... PARAM_N] [CHECKSUM] [WCHECKSUM]
```

| Campo       | Tamanho | Descrição                                          |
|-------------|---------|----------------------------------------------------|
| `STX`       | 1 byte  | Marcador de início (`0x02`), sempre único          |
| `COMMAND`   | 1 byte  | Código do comando (nunca pode ser `0x02`)          |
| `RX`        | 1 byte  | Endereço do destinatário (fixo `0x01`)             |
| `TX`        | 1 byte  | Endereço do remetente (fixo `0xFF`)                |
| `N_PARAMS`  | 1 byte  | Número de parâmetros — **máximo 255**              |
| `PARAMS`    | N bytes | Parâmetros do comando                              |
| `CHECKSUM`  | 1 byte  | Soma simples dos bytes (módulo 256)                |
| `WCHECKSUM` | 1 byte  | Checksum ponderado acumulado pelo índice           |

**Limitação arquitetural:** como `N_PARAMS` é 1 byte, o payload máximo por telegrama é 255 bytes. Com 4 bytes reservados para o número de sequência, cada bloco carrega até **251 bytes de dados**. Essa é uma restrição do protocolo industrial original, não um erro de implementação.

### Byte Stuffing

O protocolo define que `0x02` (STX) nunca pode aparecer solto dentro do telegrama, pois seria interpretado como início de um novo telegrama. A regra é:

- Qualquer `0x02` dentro do conteúdo (inclusive endereços e checksums) é **dobrado**: `0x02` → `[0x02, 0x02]`
- O receptor interpreta `0x02 0x02` como um único byte de dado `0x02`
- O receptor interpreta `0x02` isolado como marcador de início
- O stuffing é aplicado **após** o cálculo dos checksums; o unstuffing é feito **antes** da validação

### Checksums

Dois checksums são calculados sobre o payload limpo (sem STX, sem stuffing):

- **CHECKSUM:** soma acumulada de todos os bytes, módulo 256
- **WCHECKSUM:** checksum ponderado — acumula o próprio checksum a cada byte, detectando erros de transposição que o checksum simples não detecta

### Comandos Disponíveis

| Constante            | Valor  | Descrição                        |
|----------------------|--------|----------------------------------|
| `SCMD_Hello`         | `0x40` | Handshake inicial                |
| `SCMD_ReadRaw`       | `0x41` | Envio de bloco de dados          |
| `SCMD_RestartDevice` | `0x4B` | Encerramento da transmissão      |
| `SCMD_ACK`           | `0x06` | Confirmação de recebimento       |

### Fluxo de Comunicação

```
Transmissor                              Receptor
    |                                        |
    |--------- SCMD_Hello ----------------->|
    |<-------- SCMD_ACK  -------------------|  Handshake
    |                                        |
    |-- SCMD_ReadRaw [Seq=1, dados] ------->|
    |<-------- SCMD_ACK [Seq=1] ------------|  Bloco 1 confirmado
    |                                        |
    |-- SCMD_ReadRaw [Seq=2, dados] ------->|
    |<-------- SCMD_ACK [Seq=2] ------------|  Bloco 2 confirmado
    |              ...                       |
    |                                        |
    |-------- SCMD_RestartDevice ---------->|
    |<-------- SCMD_ACK  -------------------|  Encerramento
```

### Controle de Erros e Retransmissão (ARQ Stop-and-Wait)

- O transmissor aguarda o ACK de cada bloco antes de enviar o próximo.
- Em caso de timeout, o bloco é retransmitido com backoff exponencial (RTO dobra a cada timeout, limitado a 10 segundos).
- O receptor descarta silenciosamente pacotes com checksum inválido.
- Pacotes com número de sequência fora de ordem são ignorados, mas o ACK é enviado de volta.

### RTT Dinâmico

O transmissor estima o tempo de ida e volta (RTT) e ajusta o timeout de retransmissão (RTO) automaticamente:

- **EWMA** (média móvel exponencial): `rtt_medio = 0.8 × rtt_anterior + 0.2 × rtt_atual`
- **RTO:** `rtt_medio × 2.5`, com mínimo de 50 ms e máximo de 10 s
- **Filtro de Karn:** o RTT só é recalculado em transmissões sem retransmissão prévia, evitando amostras ambíguas que superestimariam o RTO

### Simulação de Falhas de Rede

O transmissor possui um simulador embutido para testes de robustez:

| Parâmetro      | Padrão  | Descrição                           |
|----------------|---------|-------------------------------------|
| `PROB_LOSS`    | `0.005` | Probabilidade de perda de pacote    |
| `PROB_CORRUPT` | `0.005` | Probabilidade de corrupção de bytes |

Em ambos os casos o transmissor loga o evento, ocorre timeout e o pacote é retransmitido automaticamente.

---

## Requisitos

- Python 3.10+
- Sem dependências externas (somente bibliotecas padrão)

---

## Como Executar

1. Coloque o arquivo `modelos_medios_dmc.png` na mesma pasta dos scripts.

2. Inicie o **receptor** em um terminal:
   ```bash
   python receptor.py
   ```

3. Em outro terminal, inicie o **transmissor**:
   ```bash
   python transmissor.py
   ```

4. Ao final da transmissão, o arquivo `recebido_modelos_dmc.png` será gerado na pasta do receptor.

---

## Configurações

| Parâmetro      | Arquivo        | Padrão      | Descrição                       |
|----------------|----------------|-------------|---------------------------------|
| `HOST`         | ambos          | `127.0.0.1` | Endereço IP                     |
| `PORT`         | ambos          | `8080`      | Porta UDP                       |
| `BUFFER_SIZE`  | transmissor.py | `200` bytes | Tamanho de cada bloco de dados  |
| `PROB_LOSS`    | transmissor.py | `0.005`     | Probabilidade de perda simulada |
| `PROB_CORRUPT` | transmissor.py | `0.005`     | Probabilidade de corrupção      |

---

## Módulos

### `protocolo_enlace.py`

Núcleo do protocolo, adaptado de driver industrial. Expõe:

- **`CriarTelegrama(command, parameters)`** — Calcula os checksums sobre o payload limpo, aplica byte stuffing (dobra `0x02` internos) e retorna o `bytearray` completo pronto para envio.
- **`Methods.ReceiveTg(code_received)`** — Localiza o STX inicial, remove o stuffing, valida os checksums e retorna `[command, parameters]` ou `None` em caso de erro.
- **`Methods.CalcChecksums(tg)`** — Calcula e retorna `[checksum, wchecksum]` para um dado payload.

### `transmissor.py`

Lê o arquivo em blocos de `BUFFER_SIZE` bytes, prefixa cada bloco com um número de sequência de 4 bytes (big-endian) e envia via `SCMD_ReadRaw`. Gerencia handshake, RTT dinâmico, retransmissões com backoff e encerramento.

### `receptor.py`

Aguarda datagramas UDP, responde ao handshake, valida checksums, ordena blocos pelo número de sequência, escreve o conteúdo no arquivo de saída e encerra ao receber `SCMD_RestartDevice`.
