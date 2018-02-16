import colorama
from opcodes import *


def get_real_address(internal_address):
    return internal_address & 0xFFFF


def get_bank_num(internal_address):
    return internal_address >> 16


def print_opcodes(chunk):
    opcode_list = chunk.opcodes
    start_addr = opcode_list[0].address
    bank_str = '' if start_addr < 0x4000 else ' (BANK 0x{:X})'.format(get_bank_num(start_addr))
    fmt_str = '0x{0:X} {1}{2}'
    header = '----- CHUNK 0x{0:X}{1} -----'.format(get_real_address(start_addr), bank_str)
    footer = '-' * len(header) + '\n'

    warning_str = ' [{}]'

    print(header)

    for op in opcode_list:
        real_address = get_real_address(op.address)
        warning = ''
        color = ''

        if op.warning is not None:
            warning = warning_str.format(op.warning)
            color = colorama.Fore.YELLOW

        if op.opcode <= 0xFF:
            tmp_op = opcodes[op.opcode]

            if op.optional_arg is not None:
                tmp_op = tmp_op.format(op.optional_arg)

            print(color + fmt_str.format(real_address, tmp_op, warning))

        else:
            print(color + fmt_str.format(real_address, ext_opcodes[op.opcode - 0xCB00], warning))

    if chunk.end_warning is not None:
        print(colorama.Fore.RED + '### {} ###'.format(chunk.end_warning))

    print(footer)
