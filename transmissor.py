from protocolo_enlace import *
import socket
import struct
import time
import random
import os

HOST            = '127.0.0.1'
PORT            = 8080
FILE_TO_SEND    = 'modelos_medios_dmc.png'
BUFFER_SIZE     = 200

PROB_LOSS       = 0.005
PROB_CORRUPT    = 0.005

def main():
    if not os.path.exists(FILE_TO_SEND):
        print(f"[!] Erro: Coloque a imagem '{FILE_TO_SEND}' nesta mesma pasta.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # --- RTT DINÂMICO SIMPLIFICADO ---
    rto             = 0.3       # Começa com 300ms
    rtt_medio       = 0.1       # Estimativa inicial de 100ms
    FATOR_SEGURANCA = 2.5       # O timeout será 2.5x o RTT médio
    
    sock.settimeout(rto)

    # --- HANDSHAKE INTERNO (SCMD_Hello) ---
    print("[*] Conectando ao receptor via SCMD_Hello...")
    while True:
        try:
            tg_hello = CriarTelegrama(SCMD_Hello, [])
            sock.sendto(tg_hello, (HOST, PORT))
            resp, addr = sock.recvfrom(2048)
            Data = Methods.ReceiveTg(bytearray(resp))
            if Data and Data[0] == SCMD_ACK:
                print("[+] Handshake firmado com sucesso!")
                break
        except socket.timeout:
            print("[!] Sem resposta do SCMD_Hello, retransmitindo...")

    # --- ENVIO COMPACTO DA IMAGEM ---
    seq_num = 1
    with open(FILE_TO_SEND, 'rb') as file:
        while True:
            chunk = file.read(BUFFER_SIZE)
            if not chunk: break
            
            seq_bytes           = list(struct.pack('!I', seq_num)) # Big-Endian Unsigned Int
            chunk_ints          = list(chunk)
            parametros_com_seq  = seq_bytes + chunk_ints
            
            ack_confirmado      = False
            retransmitido       = False
            
            while not ack_confirmado:
                rand_val = random.random()
                is_lost = rand_val < PROB_LOSS
                is_corrupted = (not is_lost) and (rand_val < (PROB_LOSS + PROB_CORRUPT))
                
                tg_dados = CriarTelegrama(SCMD_ReadRaw, parametros_com_seq)
                
                if is_corrupted:
                    tg_dados[-1] = (tg_dados[-1] + 1) & 0xFF
                    print(f" [SIMULADOR] Forçando erro de Checksum no pacote Seq={seq_num}")

                # Marca o tempo inicial apenas na primeira tentativa
                if not retransmitido:
                    t_inicio = time.time()

                if not is_lost:
                    sock.sendto(tg_dados, (HOST, PORT))
                else:
                    print(f" [SIMULADOR] Sumindo com o pacote Seq={seq_num}")

                try:
                    resp, addr = sock.recvfrom(2048)
                    Data = Methods.ReceiveTg(bytearray(resp))
                    
                    if Data and Data[0] == SCMD_ACK:
                        ack_seq = struct.unpack('!I', bytes(Data[1]))[0]
                        if ack_seq == seq_num:
                            
                            # Filtro de Karn: Só calcula RTT se não retransmitiu
                            if not retransmitido:
                                rtt_atual = time.time() - t_inicio
                                # Média móvel ponderada simples (EWMA)
                                rtt_medio = (0.8 * rtt_medio) + (0.2 * rtt_atual)
                                # Define o novo RTO com base na margem de segurança
                                rto = max(0.05, min(rtt_medio * FATOR_SEGURANCA, 10.0))
                                print(f"[+] RTT: {rtt_atual:.4f}s | RTO: {rto:.4f}s")

                            print(f"[+] Confirmação ACK recebida para o bloco Seq={seq_num}")
                            ack_confirmado = True
                            seq_num += 1
                            sock.settimeout(rto)
                            
                except socket.timeout:
                    retransmitido = True
                    rto = min(rto * 2, 10.0) # Dobra o tempo (Backoff) até o teto de 10 segundos
                    print(f"[!] Timeout no Seq={seq_num}. Novo RTO temporário: {rto:.4f}s")
                    sock.settimeout(rto)

    # --- ENCERRAMENTO (SCMD_RestartDevice) ---
    print("\n[*] Imagem finalizada. Reiniciando canal com SCMD_RestartDevice...")
    sock.settimeout(0.3)
    while True:
        try:
            tg_fin = CriarTelegrama(SCMD_RestartDevice, [])
            sock.sendto(tg_fin, (HOST, PORT))
            resp, addr = sock.recvfrom(2048)
            Data = Methods.ReceiveTg(bytearray(resp))
            if Data and Data[0] == SCMD_ACK:
                print("[+] Receptor liberado. Encerrando transmissor.")
                break
        except socket.timeout:
            pass

    sock.close()

main()