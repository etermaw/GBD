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

# opcodes that ends chunk
#          JR     JP   RET  CALL  RETI  JP(HL) RST
end_op = (0x18, 0xC3, 0xC9, 0xCD, 0xD9, 0xE9, 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)

# opcodes that causes split in following
split_op = (0xCD, 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)


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
    opcodes = chunk.split('\n')[1:][::-1]

    for op in opcodes:
        result = LOAD_BANK_NUM.search(op)

        if result is not None:
            return int(result.group(1), 16)

    return '\n~~Warning: Could not resolve new bank address!~~'


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

        if opcode in (0xC5, 0xD5, 0xE5, 0xF5):
            stack_balance += 1

        elif opcode in (0xC1, 0xD1, 0xE1, 0xF1):
            stack_balance -= 1

        if stack_balance < 0:
            warning = '\n~~Warning: Possible return address manipulation!~~'

        if opcode in end_op:
            ending = True

            if opcode in (0xC3, 0xCD):
                next_addr = get_next_addr(pc, data, bank)

            if opcode == 0x18:
                ret = get_next_addr(pc, data, bank)

                if ret > 127:
                    ret = -(256 - ret)

                next_addr = pc + ret + op_len[opcode]

            if opcode in (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF):
                next_addr = ((opcode >> 3) & 7) * 0x8

            if opcode in (0xCD, 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF):
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

        else:
            pc += op_len[opcode]

    chunk += el * '-'
    chunk += warning

    return chunk, next_addr, bank, stack_balance


current_pc = int(sys.argv[2], 16)
depth = 0
MAX_DEPTH = int(sys.argv[3])
data = []
stack = []
current_bank = 1
stack_balance = 0

with open(sys.argv[1], 'rb') as f:
    data = f.read()

while depth < MAX_DEPTH:
    if current_pc > 0x4000 and isinstance(current_bank, str):
        print('Error: bank changed in runtime!')
        break

    root, current_pc, current_bank, stack_balance = get_chunk(current_pc, data, stack, current_bank, stack_balance)
    root += '\n\n'
    depth += 1

    if isinstance(current_pc, str):
        root += current_pc + '\n'
        print(root)
        break

    elif current_pc >= 0x8000:
        # root += 'Dynamic Execution: program go out of ROM!\n'
        # print(root)
        # break
        current_pc -= 0x8000

    print(root)