def mbc_mapper(bank_num):
    if bank_num & 0x1F == 0:
        bank_num |= 0x1

    return bank_num


def mbc5_mapper(bank_num):
    return bank_num


def get_new_bank(opcode_list):
    for op in reversed(opcode_list):
        if op.opcode == 0x3E:  # if opcode == 'LD A,(0x0 ~ 0xFF)'
            return mbc_mapper(op.optional_arg)

        elif op.opcode == 0xAF:  # opcode == XOR A,A
            return mbc_mapper(0)

    raise Exception('Could not resolve new bank adress!')


def get_hl_mod(opcode_list):
    hval = None
    lval = None

    for op in reversed(opcode_list):
        if op.opcode == 0x21:  # if opcode == 'LD HL,(0x0000 ~ 0xFFFF)'
            return op.optional_arg

        elif op.opcode == 0x26 and hval is not None:  # if opcode == 'LD H,(0x0 ~ 0xFF)'
            hval = op.optional_arg

            if lval is not None:
                return (hval << 8) | lval

        elif op.opcode == 0x2E and lval is not None:  # if opcode == 'LD L,(0x0 ~ 0xFF)'
            lval = op.optional_arg

            if hval is not None:
                return (hval << 8) | lval

    raise Exception('Could not resolve HL value!')
