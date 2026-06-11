from protocolo_enlace import *
import socket
import struct

HOST = '127.0.0.1'
PORT = 8080
OUTPUT_FILE = 'recebido_modelos_dmc.png'

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"[*] Receptor escutando em {HOST}:{PORT}...")

    expected_seq = 1
    client_addr = None
    file_ptr = open(OUTPUT_FILE, 'wb')

    try:
        while True:
            packet, addr = sock.recvfrom(2048)
            
            Data = Methods.ReceiveTg(bytearray(packet))
            
            if Data is None:
                print("[!] BAD CHECK SUMS detectado pelo receptor! Descartando lixo de rede...")
            else: 
                command, parameters = Data

            if command == SCMD_Hello:
                client_addr = addr
                print(f"[+] SCMD_Hello vindo de {addr}. Respondendo com SCMD_ACK...")
                tg_ack = CriarTelegrama(SCMD_ACK, [])
                sock.sendto(tg_ack, client_addr)

            elif command == SCMD_ReadRaw and addr == client_addr:
                # Extrai os 4 primeiros bytes como o número de sequência do pacote
                seq_num = struct.unpack('!I', bytes(parameters[:4]))[0]
                payload_imagem = bytes(parameters[4:])
                
                if seq_num == expected_seq:
                    file_ptr.write(payload_imagem)
                    print(f" [+] Gravado bloco Seq={seq_num} com sucesso.")
                    expected_seq += 1
                
                # Responde confirmando o pacote atual
                param_ack = list(struct.pack('!I', seq_num))
                tg_ack = CriarTelegrama(SCMD_ACK, param_ack)
                sock.sendto(tg_ack, client_addr)

            elif command == SCMD_RestartDevice and addr == client_addr:
                print("\n[+] SCMD_RestartDevice recebido. Finalizando escrita...")
                tg_ack = CriarTelegrama(SCMD_ACK, [])
                sock.sendto(tg_ack, client_addr)
                break

    finally:
        file_ptr.close()
        sock.close()
        print(f"[+] Arquivo '{OUTPUT_FILE}' gerado sem corrupções através do protocolo do driver.")

main()