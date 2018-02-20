import colorama
from opcodes import *

HW_REGISTERS = {0x00: "JOYP", 0x01: "SB", 0x02: "SC", 0x04: "DIV",
                0x05: "TIMA", 0x06: "TMA", 0x07: "TAC", 0x0f: "IF",
                0x10: "NR10", 0x11: "NR11", 0x12: "NR12", 0x13: "NR13",
                0x14: "NR14", 0x16: "NR21", 0x17: "NR22", 0x18: "NR23",
                0x19: "NR24", 0x1a: "NR30", 0x1b: "NR31", 0x1c: "NR32",
                0x1d: "NR33", 0x1e: "NR34", 0x20: "NR41", 0x21: "NR42",
                0x22: "NR43", 0x23: "NR44", 0x24: "NR50", 0x25: "NR51",
                0x26: "NR52", 0x40: "LCDC", 0x41: "STAT", 0x42: "SCY",
                0x43: "SCX", 0x44: "LY", 0x45: "LYC", 0x46: "DMA",
                0x47: "BGP", 0x48: "OBP0", 0x49: "OBP1", 0x4a: "WY",
                0x4b: "WX", 0x4d: "KEY1", 0x4f: "VBK", 0x51: "HDMA1",
                0x52: "HDMA2", 0x53: "HDMA3", 0x54: "HDMA4", 0x55: "HDMA5",
                0x56: "RP", 0x68: "BGPI", 0x69: "BGPD", 0x6a: "OBPI",
                0x6b: "OBPD", 0x6c: "UNKNOWN1", 0x70: "SVBK", 0x72: "UNKNOWN2",
                0x73: "UNKNOWN3", 0x74: "UNKNOWN4", 0x75: "UNKNOWN5", 0x76: "UNKNOWN6",
                0x77: "UNKNOWN7", 0xff: "IE"}

JR_FAMILY = {0x18, 0x20, 0x28, 0x30, 0x38}


def u8_correction(value):
    if value > 127:
        value -= 256

    return value


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

        elif op.info is not None:
            warning = warning_str.format(op.info)
            color = colorama.Fore.GREEN

        if op.opcode <= 0xFF:
            if op.opcode in (0xE0, 0xF0) and op.optional_arg in HW_REGISTERS:
                warning = warning_str.format(HW_REGISTERS[op.optional_arg])
                color = colorama.Fore.CYAN

            elif op.opcode in JR_FAMILY:
                warning = warning_str.format(hex(get_real_address(op.address) + u8_correction(op.optional_arg) + 2))
                color = colorama.Fore.GREEN

            tmp_op = opcodes[op.opcode]

            if op.optional_arg is not None:
                tmp_op = tmp_op.format(op.optional_arg)

            print(color + fmt_str.format(real_address, tmp_op, warning))

        else:
            print(color + fmt_str.format(real_address, ext_opcodes[op.opcode - 0xCB00], warning))

    if chunk.end_warning is not None:
        print(colorama.Fore.RED + '### {} ###'.format(chunk.end_warning))

    print(footer)
