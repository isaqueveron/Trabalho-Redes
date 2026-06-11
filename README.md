# Protocolo de Enlace com Transferência de Imagem via UDP

Implementação de um protocolo de enlace customizado com transferência confiável de dados sobre UDP, incluindo detecção de erros por checksum, retransmissão automática (ARQ Stop-and-Wait) e RTT dinâmico com algoritmo de Karn.

---

## Estrutura dos Arquivos

```
.
├── protocolo_enlace.py   # Núcleo do protocolo: criação e validação de telegramas
├── transmissor.py        # Lado cliente: lê a imagem e a envia em blocos
├── receptor.py           # Lado servidor: recebe os blocos e reconstrói a imagem
└── modelos_medios_dmc.png  # Imagem de entrada (deve ser fornecida pelo usuário)
```

---

## Como Funciona

### Formato do Telegrama

Cada mensagem trocada entre transmissor e receptor segue o formato abaixo:

```
[STX] [COMMAND] [RX] [TX] [N_PARAMS] [PARAM_0 ... PARAM_N] [CHECKSUM] [WCHECKSUM]
```

| Campo       | Tamanho  | Descrição                                      |
|-------------|----------|------------------------------------------------|
| `STX`       | 1–2 bytes | Marcador de início (`0x02`). Duplicado se presente no payload |
| `COMMAND`   | 1 byte   | Código do comando                              |
| `RX`        | 1 byte   | Endereço do destinatário (fixo `0x01`)         |
| `TX`        | 1 byte   | Endereço do remetente (fixo `0xFF`)            |
| `N_PARAMS`  | 1 byte   | Número de parâmetros                           |
| `PARAMS`    | N bytes  | Parâmetros do comando                          |
| `CHECKSUM`  | 1 byte   | Soma simples dos bytes (módulo 256)            |
| `WCHECKSUM` | 1 byte   | Checksum ponderado pelo índice                 |

### Comandos Disponíveis

| Constante             | Valor  | Descrição                          |
|-----------------------|--------|------------------------------------|
| `SCMD_Hello`          | `0x40` | Handshake inicial                  |
| `SCMD_ReadRaw`        | `0x41` | Envio de bloco de dados (imagem)   |
| `SCMD_RestartDevice`  | `0x4B` | Encerramento da transmissão        |
| `SCMD_ACK`            | `0x06` | Confirmação de recebimento         |

### Fluxo de Comunicação

```
Transmissor                          Receptor
    |                                    |
    |-------- SCMD_Hello  -------------->|
    |<-------- SCMD_ACK  ----------------|  Handshake
    |                                    |
    |-- SCMD_ReadRaw [Seq=1, dados] ---->|
    |<-------- SCMD_ACK [Seq=1] ---------|  Bloco 1 confirmado
    |                                    |
    |-- SCMD_ReadRaw [Seq=2, dados] ---->|
    |<-------- SCMD_ACK [Seq=2] ---------|  Bloco 2 confirmado
    |            ...                     |
    |                                    |
    |------ SCMD_RestartDevice --------->|
    |<-------- SCMD_ACK  ----------------|  Encerramento
```

### Controle de Erros e Retransmissão (ARQ Stop-and-Wait)

- O transmissor aguarda o ACK de cada bloco antes de enviar o próximo.
- Em caso de **timeout**, o bloco é retransmitido com backoff exponencial (dobra o RTO, limitado a 10 segundos).
- O receptor descarta pacotes com checksum inválido.
- Pacotes com número de sequência fora de ordem são ignorados (mas o ACK é enviado de volta).

### RTT Dinâmico

O transmissor estima o tempo de ida e volta (RTT) e ajusta o timeout de retransmissão (RTO) automaticamente:

- **EWMA** (média móvel exponencial): `rtt_medio = 0.8 × rtt_anterior + 0.2 × rtt_atual`
- **RTO**: `rtt_medio × 2.5`, com mínimo de 50ms e máximo de 10s
- **Filtro de Karn**: o RTT só é recalculado em transmissões sem retransmissão prévia, evitando amostras ambíguas

### Simulação de Falhas de Rede

O transmissor possui um simulador embutido para testes de robustez:

| Parâmetro     | Padrão  | Descrição                          |
|---------------|---------|------------------------------------|
| `PROB_LOSS`   | `0.005` | Probabilidade de perda de pacote   |
| `PROB_CORRUPT`| `0.005` | Probabilidade de corrupção de bytes |

---

## Requisitos

- Python 3.10+
- Sem dependências externas (somente bibliotecas padrão)

---

## Como Executar

1. Coloque a imagem `modelos_medios_dmc.png` na mesma pasta dos scripts.

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

| Parâmetro      | Arquivo          | Padrão        | Descrição                        |
|----------------|------------------|---------------|----------------------------------|
| `HOST`         | ambos            | `127.0.0.1`   | Endereço IP                      |
| `PORT`         | ambos            | `8080`        | Porta UDP                        |
| `BUFFER_SIZE`  | transmissor.py   | `200` bytes   | Tamanho de cada bloco de dados   |
| `PROB_LOSS`    | transmissor.py   | `0.005`       | Probabilidade de perda simulada  |
| `PROB_CORRUPT` | transmissor.py   | `0.005`       | Probabilidade de corrupção       |

---

## Módulos

### `protocolo_enlace.py`

Núcleo do protocolo. Expõe:

- **`CriarTelegrama(command, parameters)`** — Monta e retorna um `bytearray` completo com STX, cabeçalho, parâmetros e checksums. Aplica byte stuffing se `STX` (`0x02`) aparecer no payload.
- **`Methods.ReceiveTg(code_received)`** — Faz o parse de um `bytearray` recebido, valida os checksums e retorna `[command, parameters]` ou `None` em caso de erro.
- **`Methods.CalcChecksums(tg)`** — Calcula e retorna `[checksum, wchecksum]` para um dado payload.

### `transmissor.py`

Lê a imagem em blocos de `BUFFER_SIZE` bytes, adiciona um número de sequência de 4 bytes (big-endian) no início de cada bloco e os envia usando `SCMD_ReadRaw`. Gerencia handshake, retransmissões e encerramento.

### `receptor.py`

Aguarda conexões UDP, responde ao handshake, valida e ordena os blocos recebidos pelo número de sequência, escreve o conteúdo no arquivo de saída e encerra ao receber `SCMD_RestartDevice`.
