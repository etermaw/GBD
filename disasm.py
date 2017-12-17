import sys
import bintrees
from opcodes import *
from rang import *

# opcode families
PUSH_FAMILY = (0xC5, 0xD5, 0xE5, 0xF5)
POP_FAMILY = (0xC1, 0xD1, 0xE1, 0xF1)
RST_FAMILY = (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)
CALL_FAMILY = (0xCD,) + RST_FAMILY
JUMP_FAMILY = (0x18, 0xC3, 0xCD)
RET_FAMILY = (0xC9, 0xD9)

JR_COND_FAMILY = (0x20, 0x28, 0x30, 0x38)
RET_COND_FAMILY = (0xC0, 0xC8, 0xD0, 0xD8)
JP_COND_FAMILY = (0xC2, 0xCA, 0xD2, 0xDA)
CALL_COND_FAMILY = (0xC4, 0xCC, 0xD4, 0xDC)

# opcodes that ends chunk
#          JR     JP   RET  CALL  RETI  JP(HL) RST
end_op = (0x18, 0xC3, 0xC9, 0xCD, 0xD9, 0xE9, 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)

# opcodes that causes split in path
split_op = JR_COND_FAMILY + RET_COND_FAMILY + JP_COND_FAMILY + CALL_COND_FAMILY


def get_byte(pc, data, bank):
    if pc < 0x4000:
        return data[pc]

    else:
        return data[(pc - 0x4000) + 0x4000 * bank]


def get_new_bank(opcode_list):
    ops = opcode_list[::-1]

    for op in ops:
        if not op[1] and op[2] == 0x3E:  # if opcode == 'LD A,(0x0 ~ 0xFF)'
            return op[3]

    raise Exception('\n~~ Warning: Could not resolve new bank adress! ~~')


def get_hl_mod(opcode_list):
    ops = opcode_list[::-1]
    hval = None
    lval = None

    for op in ops:
        if not op[1] and op[2] == 0x21:  # if opcode == 'LD HL,(0x0000 ~ 0xFFFF)'
            return op[3]

        elif not op[1] and op[2] == 0x26 and hval is not None:  # if opcode == 'LD H,(0x0 ~ 0xFF)'
            hval = op[3]

            if lval is not None:
                return (hval << 8) | lval

        elif not op[1] and op[2] == 0x2E and lval is not None:  # if opcode == 'LD L,(0x0 ~ 0xFF)'
            lval = op[3]

            if hval is not None:
                return (hval << 8) | lval

    return '\nCould not resolve HL value!'


def get_single_op(pc, data, bank):
    is_extended = False
    opcode = get_byte(pc, data, bank)
    optional_arg = None

    if opcode == 0xCB:
        opcode = get_byte(pc + 1, data, bank)
        is_extended = True

    else:
        if op_len[opcode] == 2:
            optional_arg = get_byte(pc + 1, data, bank)

        elif op_len[opcode] == 3:
            optional_arg = (get_byte(pc + 2, data, bank) << 8) | get_byte(pc + 1, data, bank)

    # internal opcode representation:
    # (address, is_extended, opcode, optional_arg)
    return pc, is_extended, opcode, optional_arg


def get_chunk(pc, data, bank, stack, stack_balance):
    chunk_start = pc
    ending = False
    chunk_opcodes = []
    next_addr = None

    while not ending:
        op = get_single_op(pc, data, bank)

        # if LD A, (0x2000 ~ 0x3FFF) [change bank command]
        if not op[1] and op[2] == 0xEA and 0x2000 <= op[3] <= 0x3FFF:
            try:
                new_bank = get_new_bank(chunk_opcodes)
                bank = new_bank

            except Exception as e:
                warning = e.args[0]

        chunk_opcodes.append(op)

        if not op[1] and op[2] in PUSH_FAMILY:
            stack_balance += 1

        elif not op[1] and op[2] in POP_FAMILY:
            stack_balance -= 1

        if stack_balance < 0:
            warning = '\n~~ Warning: Possible return address manipulation! ~~'

        if not op[1] and op[2] in end_op:
            ending = True

            if op[2] in JUMP_FAMILY:
                next_addr = op[3]

                if op[2] == 0x18:
                    ret = next_addr

                    if ret > 127:
                        ret = -(256 - ret)

                    next_addr = pc + ret + 2  # JR length is always 2

            if op[2] in RST_FAMILY:
                next_addr = ((op[2] >> 3) & 7) * 0x8

            if op[2] in CALL_FAMILY:
                # next_addr is handled in JUMP_FAMILY condition
                stack.append((pc + op_len[op[2]], stack_balance))
                stack_balance = 0

            if op[2] in RET_FAMILY:
                if len(stack) == 0:
                    next_addr = 'Stack underflow!'

                elif stack_balance < 0:
                    next_addr = 'Detected stack manipulation: chunk pops return address!'

                elif stack_balance > 0:
                    next_addr = 'Detected stack manipulation: chunk pushes new return address!'

                else:
                    next_addr, stack_balance = stack[-1]
                    stack.pop()

            if op[2] == 0xE9:
                next_addr = get_hl_mod(chunk_opcodes)

        pc += op_len[op[2]]

    chunk_end = pc - 1

    return Rang(chunk_start, chunk_end), chunk_opcodes, next_addr, bank, stack_balance


def follow_path(data, pc, bank, visited_chunks, local_stack = [], local_stack_balance = 0, max_depth = None):
    depth = 0
    MAX_DEPTH = max_depth if max_depth is not None else 999999999

    while depth < MAX_DEPTH:
        if pc >= 0x4000 and isinstance(bank, str):
            print('Error: bank changed in runtime!')
            break

        chunk_range, op_list, pc, bank, local_stack_balance = get_chunk(pc, data, bank, local_stack, local_stack_balance)
        depth += 1

        if chunk_range.start in visited_chunks:
            break

        else:
            visited_chunks.insert(chunk_range, op_list)

        if isinstance(pc, str):
            print_opcodes(op_list)
            print(pc + '\n')
            break

        elif pc >= 0x8000:
            print_opcodes(op_list)
            print('Dynamic Execution: program go out of ROM!\n')
            break

        print_opcodes(op_list)


def print_opcodes(opcode_list):
    fmt_str = '0x{0:X} {1}'
    header = '----- CHUNK 0x{0:X} -----'.format(opcode_list[0][0])
    footer = '-' * len(header) + '\n'

    print(header)

    for op in opcode_list:
        if not op[1]:
            tmp_op = opcodes[op[2]]

            if op[3] is not None:
                tmp_op = tmp_op.format(op[3])

            print(fmt_str.format(op[0], tmp_op))

        else:
            print(fmt_str.format(op[0], ext_opcodes[op[2]]))

    print(footer)


binary = []
chunks = bintrees.RBTree()

with open(sys.argv[1], 'rb') as file:
    binary = file.read()

follow_path(binary, int(sys.argv[2], 16), 1, chunks, max_depth=int(sys.argv[3]))
