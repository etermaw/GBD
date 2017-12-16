import sys
import re
from opcodes import *

# regex for resolving static bank change
LOAD_BANK_NUM = re.compile('LD A,(0x[\dA-F]+)')
CHANGE_BANK = re.compile('LD \(0x[2-3][\dA-F]{3}\),A')

# regex for resolving static jump to address pointed by HL
LOAD_HL = re.compile('LD HL,\((0x[\dA-F]{1,4})\)')
LOAD_H = re.compile('LD H,(0x[\dA-F]{1,2})')
LOAD_L = re.compile('LD L,(0x[\dA-F]{1,2})')

# opcode families
PUSH_FAMILY = (0xC5, 0xD5, 0xE5, 0xF5)
POP_FAMILY = (0xC1, 0xD1, 0xE1, 0xF1)
RST_FAMILY = (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)
CALL_FAMILY = (0xCD,) + RST_FAMILY
JUMP_FAMILY = (0x18, 0xC3, 0xCD)

# opcodes that ends chunk
#          JR     JP   RET  CALL  RETI  JP(HL) RST
end_op = (0x18, 0xC3, 0xC9, 0xCD, 0xD9, 0xE9, 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)

# opcodes that causes split in path
#          |     JR [COND], r8     |     RET [COND]        |      JP [COND], r16   |    CALL [COND], a16
split_op = (0x20, 0x28, 0x30, 0x38, 0xC0, 0xC8, 0xD0, 0xD8, 0xC2, 0xCA, 0xD2, 0xDA, 0xC4, 0xCC, 0xD4, 0xDC)


def get_byte(pc, data, bank):
    if pc < 0x4000:
        return data[pc]

    else:
        return data[(pc - 0x4000) + 0x4000 * bank]


def decode(byte1, byte2):
    if byte1 != 0xCB:
        return opcodes[byte1]

    else:
        return ext_opcodes[byte2]


def get_new_bank(chunk):
    ops = chunk.split('\n')[1:][::-1]

    for op in ops:
        result = LOAD_BANK_NUM.search(op)

        if result is not None:
            return int(result.group(1), 16)

    return '\n~~Warning: Could not resolve new bank address!~~'


def get_hl_mod(chunk):
    ops = chunk.split('\n')[1:][::-1]
    hval = None
    lval = None

    for op in ops:
        hl = LOAD_HL.search(op)
        h = LOAD_H.search(op)
        l = LOAD_L.search(op)

        if hl is not None:
            return int(hl.group(1), 16)

        elif h is not None and hval is not None:
            hval = int(h.group(1), 16)

            if lval is not None:
                return (hval << 8) | lval

        elif l is not None and lval is not None:
            lval = int(l.group(1), 16)

            if hval is not None:
                return (hval << 8) | lval

    return '\nCould not resolve HL value!'


def get_next_addr(pc, data, bank):
    if op_len[get_byte(pc, data, bank)] == 2:
        return get_byte(pc + 1, data, bank)

    elif op_len[get_byte(pc, data, bank)] == 3:
        return (get_byte(pc + 2, data, bank) << 8) | get_byte(pc + 1, data, bank)


def get_single_op(pc, data, bank):
    ret = '0x{0:X} {1}'.format(pc, decode(get_byte(pc, data, bank), get_byte(pc + 1, data, bank)))

    if op_len[get_byte(pc, data, bank)] == 2:
        ret = ret.format(get_byte(pc + 1, data, bank))

    elif op_len[get_byte(pc, data, bank)] == 3:
        ret = ret.format((get_byte(pc + 2, data, bank) << 8) | get_byte(pc + 1, data, bank))

    return ret


def get_chunk(pc, data, stack, bank, stack_balance):
    chunk = '---CHUNK 0x{0:X}---\n'.format(pc)
    el = len(chunk) - 1
    ending = False
    next_addr = 'Cannot go deeper!'
    warning = ''

    while not ending:
        opcode = get_byte(pc, data, bank)
        op = get_single_op(pc, data, bank) + '\n'

        if CHANGE_BANK.search(op):
            new_bank = get_new_bank(chunk)

            if not isinstance(new_bank, str):
                warning = '\n~~Bank switch from 0x{0:X} to 0x{1:X}~~'.format(bank, new_bank)

            else:
                warning = new_bank

            bank = new_bank

        chunk += op

        if opcode in PUSH_FAMILY:
            stack_balance += 1

        elif opcode in POP_FAMILY:
            stack_balance -= 1

        if stack_balance < 0:
            warning = '\n~~Warning: Possible return address manipulation!~~'

        if opcode in end_op:
            ending = True

            if opcode in JUMP_FAMILY:
                next_addr = get_next_addr(pc, data, bank)

                if opcode == 0x18:
                    ret = next_addr

                    if ret > 127:
                        ret = -(256 - ret)

                    next_addr = pc + ret + op_len[opcode]

            if opcode in RST_FAMILY:
                next_addr = ((opcode >> 3) & 7) * 0x8

            if opcode in CALL_FAMILY:
                stack.append((pc + op_len[opcode], stack_balance))
                stack_balance = 0

            if opcode == 0xC9:
                if len(stack) == 0:
                    next_addr = 'Stack underflow!'

                elif stack_balance < 0:
                    next_addr = 'Detected stack manipulation: chunk pops return address!'

                elif stack_balance > 0:
                    next_addr = 'Detected stack manipulation: chunk pushes new return address!'

                else:
                    next_addr, stack_balance = stack[-1]
                    stack.pop()

            if opcode == 0xE9:
                next_addr = get_hl_mod(chunk)

        else:
            pc += op_len[opcode]

    chunk += el * '-'
    chunk += warning

    return chunk, next_addr, bank, stack_balance


def follow_path(data, pc, bank, local_stack = [], local_stack_balance = 0, max_depth = None):
    depth = 0
    MAX_DEPTH = max_depth if max_depth is not None else 999999999

    while depth < MAX_DEPTH:
        if pc >= 0x4000 and isinstance(bank, str):
            print('Error: bank changed in runtime!')
            break

        root, pc, bank, local_stack_balance = get_chunk(pc, data, local_stack, bank, local_stack_balance)
        root += '\n\n'
        depth += 1

        if isinstance(pc, str):
            root += pc + '\n'
            print(root)
            break

        elif pc >= 0x8000:
            # root += 'Dynamic Execution: program go out of ROM!\n'
            # print(root)
            # break
            pc -= 0x8000

        print(root)


binary = []

with open(sys.argv[1], 'rb') as file:
    binary = file.read()

follow_path(binary, int(sys.argv[2], 16), 1, max_depth=int(sys.argv[3]))
