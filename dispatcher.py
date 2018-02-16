A_MODS = {0xA, 0x1A, 0x2A, 0x3A, 0xF0, 0xF1, 0xF2, 0xC6, 0xD6, 0xE6, 0xF6, 0xFA, 0xCE, 0xDE, 0xEE} | \
         set(range(0x77, 0xB8)) | \
         set([0xCB07 + x*0x10 for x in range(0, 0x10)]) | \
         set([0xCB0F + x*0x10 for x in range(0, 0x10)])

HL_MODS = set(range(0x60, 0x70)) | \
          set([0xCB05 + i*0x10 for i in range(0, 0x10)]) | \
          set([0xCB06 + i*0x10 for i in range(0, 0x10)]) | \
          set([0xCB0C + i*0x10 for i in range(0, 0x10)]) | \
          set([0xCB0D + i*0x10 for i in range(0, 0x10)]) | \
          {0x09, 0x19, 0x29, 0x39, 0xE1, 0xF8}


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

        elif op.opcode in A_MODS:  # register A got modified, abort dispatching
            op.warning = 'Bank resolving aborted here'
            break

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

        elif op.opcode in HL_MODS:
            op.warning = 'HL resolving aborted here'
            break

    raise Exception('Could not resolve HL value!')
