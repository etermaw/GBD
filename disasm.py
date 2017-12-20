import sys
import bintrees
from opcodes import *
from helpers import *

# opcode families
PUSH_FAMILY = (0xC5, 0xD5, 0xE5, 0xF5)
POP_FAMILY = (0xC1, 0xD1, 0xE1, 0xF1)
RST_FAMILY = (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)
CALL_FAMILY = (0xCD,) + RST_FAMILY
JUMP_FAMILY = (0x18, 0xC3)
RET_FAMILY = (0xC9, 0xD9)

JR_COND_FAMILY = (0x20, 0x28, 0x30, 0x38)
RET_COND_FAMILY = (0xC0, 0xC8, 0xD0, 0xD8)
JP_COND_FAMILY = (0xC2, 0xCA, 0xD2, 0xDA)
CALL_COND_FAMILY = (0xC4, 0xCC, 0xD4, 0xDC)

# opcodes that ends chunk
#       JP(HL)
end_op = (0xE9,) + JUMP_FAMILY + RET_FAMILY

# opcodes that causes split in path
split_op = ()  # JR_COND_FAMILY + JP_COND_FAMILY + CALL_COND_FAMILY + CALL_FAMILY


def get_byte(pc, data, bank):
    if pc < 0x4000:
        return data[pc]

    else:
        return data[(pc - 0x4000) + 0x4000 * bank]


def get_new_bank(opcode_list):
    ops = opcode_list[::-1]

    for op in ops:
        if op.opcode == 0x3E:  # if opcode == 'LD A,(0x0 ~ 0xFF)'
            return op.optional_arg

    raise Exception('\n~~ Warning: Could not resolve new bank adress! ~~')


def calculate_internal_address(pc, bank):
    if pc < 0x4000:
        return pc

    else:
        return (bank << 16) | pc


def get_real_address(internal_address):
    return internal_address & 0xFFFF


def get_hl_mod(opcode_list):
    ops = opcode_list[::-1]
    hval = None
    lval = None

    for op in ops:
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

    return '\nCould not resolve HL value!'


def merge_chunks(chunk1: [Opcode], chunk2: [Opcode]):
    s1, s2 = chunk1[0].address, chunk2[0].address
    e1, e2 = chunk1[-1].address, chunk2[-1].address

    if s2 <= e1:
        i1 = chunk1.index(s2)
        return chunk1[0:i1] + chunk2

    elif s1 <= e2:
        i1 = chunk2.index(s1)
        return chunk1[0:i1] + chunk2

    else:
        raise Exception('Trying to merge two separate chunks!')


def get_single_op(pc, data, bank):
    opcode = get_byte(pc, data, bank)
    optional_arg = None
    op_length = op_len[opcode]

    if opcode == 0xCB:
        opcode = 0xCB00 + get_byte(pc + 1, data, bank)
        op_length = 2

    else:
        if op_length == 2:
            optional_arg = get_byte(pc + 1, data, bank)

        elif op_length == 3:
            optional_arg = (get_byte(pc + 2, data, bank) << 8) | get_byte(pc + 1, data, bank)

    return Opcode(calculate_internal_address(pc, bank), opcode, optional_arg, op_length)


def get_chunk(pc, data, bank, stack, stack_balance, visit_que, visited_chunks):
    chunk_start = pc
    ending = False
    chunk_opcodes = []
    next_addr = None

    while not ending:
        op = get_single_op(pc, data, bank)

        # if LD A, (0x2000 ~ 0x3FFF) [change bank command]
        if op.opcode == 0xEA and 0x2000 <= op.optional_arg <= 0x3FFF:
            try:
                new_bank = get_new_bank(chunk_opcodes)
                bank = new_bank

            except Exception as e:
                warning = e.args[0]

        chunk_opcodes.append(op)

        if op.opcode in PUSH_FAMILY:
            stack_balance += 1

        elif op.opcode in POP_FAMILY:
            stack_balance -= 1

        if stack_balance < 0:
            warning = '\n~~ Warning: Possible return address manipulation! ~~'

        if op.opcode in end_op:
            ending = True

            if op.opcode in JUMP_FAMILY:
                next_addr = op.optional_arg

                if op.opcode == 0x18:
                    ret = next_addr

                    if ret > 127:
                        ret = ret - 256

                    next_addr = pc + ret + 2  # JR length is always 2

            elif op.opcode == 0xE9:
                next_addr = get_hl_mod(chunk_opcodes)

            else:
                if len(stack) == 0:
                    next_addr = 'Stack underflow!'

                elif stack_balance < 0:
                    next_addr = 'Detected stack manipulation: chunk pops return address!'

                elif stack_balance > 0:
                    next_addr = 'Detected stack manipulation: chunk pushes new return address!'

                else:
                    next_addr, stack_balance = stack[-1]
                    stack.pop()

        pc += op.opcode_len

    chunk_end = pc - 1

    return Rang(chunk_start, chunk_end), chunk_opcodes, next_addr, bank, stack_balance


def follow_path(data, pc, bank, visited_chunks, visit_que, local_stack=[], local_stack_balance=0, max_depth=None):
    depth = 0
    MAX_DEPTH = max_depth if max_depth is not None else 999999999

    while depth < MAX_DEPTH:
        if pc >= 0x4000 and isinstance(bank, str):
            print('Error: bank changed in runtime!')
            break

        chunk_range, op_list, pc, bank, local_stack_balance = get_chunk(pc, data, bank, local_stack, local_stack_balance, visit_que, visited_chunks)
        depth += 1

        if chunk_range.start in visited_chunks:
            break

        else:
            if chunk_range.end in visited_chunks:
                old = visited_chunks[chunk_range.end]
                new = merge_chunks(op_list, old)
                visited_chunks.remove(chunk_range.end)
                visited_chunks.insert(Rang(new[0].address, new[-1].address), new)

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
    header = '----- CHUNK 0x{0:X} -----'.format(get_real_address(opcode_list[0].address))
    footer = '-' * len(header) + '\n'

    print(header)

    for op in opcode_list:
        real_address = get_real_address(op.address)

        if op.opcode <= 0xFF:
            tmp_op = opcodes[op.opcode]

            if op.optional_arg is not None:
                tmp_op = tmp_op.format(op.optional_arg)

            print(fmt_str.format(real_address, tmp_op))

        else:
            print(fmt_str.format(real_address, ext_opcodes[op.opcode - 0xCB00]))

    print(footer)


binary = []
chunks = bintrees.RBTree()
visit_queue = []

with open(sys.argv[1], 'rb') as file:
    binary = file.read()


follow_path(binary, int(sys.argv[2], 16), 1, chunks, visit_queue, max_depth=int(sys.argv[3]))
