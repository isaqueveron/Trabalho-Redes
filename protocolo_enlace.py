STX =                           0x02
SCMD_ACK =                      0x06
SCMD_Hello =                    0x40
SCMD_ReadRaw =                  0x41
SCMD_RestartDevice  =           0x4B

class Methods:
    def CalcChecksums(tg: list[int]) -> list[int]:
        """
        Calculate the checksum and the weigthed checksum of a given 
        telegram without the STX bytes.

        Args: 
            tg (list[int]): The telegram excluding STX.
        Returns: 
            list(checksum, wchecksum): Where checksum is the sum of the bytes, and wchecksum is the weigthed checksum
        of the bytes based on its index
        """
        checksum = 0
        wchecksum = 0
        for itm in tg:
            checksum = (checksum + itm) & 0xFF
            wchecksum += checksum
            if wchecksum > 0xFF: 
                wchecksum += 1
            wchecksum &= 0xFF
        return [checksum, wchecksum]

    def ReceiveTg(code_received: bytearray) -> list:
        """
        Processes the received bytearray, handles byte stuffing, 
        and validates checksums before extracting the command and parameters.

        Args:
            code_received (bytearray): Bytearray read from the serial port.
        Returns:
            (list[int, list[int]]): Command and unstuffed parameters list.
        """
        if not code_received: return None
        try:
            start_idx = code_received.index(0x02)
            while start_idx < len(code_received) and code_received[start_idx] == 0x02:
                start_idx += 1
            tg_to_process = code_received[start_idx:]
        except ValueError:
            return None

        clean_data = tg_to_process
        payload = clean_data[:-2]
        received_cs = clean_data[-2:]
        
        if Methods.CalcChecksums(payload) == list(received_cs):
            command = clean_data[0]
            num_params = clean_data[3]
            parameters = clean_data[4:4+num_params]
            return [command, parameters]
        else:
            return None

def CriarTelegrama(command: int, parameters: list[int]) -> bytearray:
    global STX
    rx = 0x01 
    tx = 0xff 
    nbr_par = len(parameters)
    
    telegram = [command, rx, tx, nbr_par]
    for i in parameters:
        telegram.append(i)
        
    checksums = Methods.CalcChecksums(telegram)
    full_unstuffed = telegram + checksums
    if STX in full_unstuffed:    
        return bytearray([STX, STX] + full_unstuffed)
    else:
        return bytearray([STX] + full_unstuffed)