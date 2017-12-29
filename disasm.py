import sys
import bintrees
from opcodes import *
from helpers import *

# opcode families
PUSH_FAMILY = (0xC5, 0xD5, 0xE5, 0xF5)
POP_FAMILY = (0xC1, 0xD1, 0xE1, 0xF1)
RST_FAMILY = (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF)
JUMP_FAMILY = (0x18, 0xC3)
RET_FAMILY = (0xC9, 0xD9)

JR_COND_FAMILY = (0x20, 0x28, 0x30, 0x38)
RET_COND_FAMILY = (0xC0, 0xC8, 0xD0, 0xD8)
JP_COND_FAMILY = (0xC2, 0xCA, 0xD2, 0xDA)
CALL_FAMILY = (0xCD, 0xC4, 0xCC, 0xD4, 0xDC)

# opcodes that ends chunk
#       JP(HL)
end_op = (0xE9,) + JUMP_FAMILY + RET_FAMILY

# opcodes that causes split in path
split_op = JR_COND_FAMILY + JP_COND_FAMILY + CALL_FAMILY


def u8_correction(value):
    if value > 127:
        value -= 256

    return value


def get_byte(pc, data, bank):
    if pc < 0x4000:
        return data[pc]

    else:
        return data[(pc - 0x4000) + 0x4000 * bank]


def get_new_bank(opcode_list):
    for op in reversed(opcode_list):
        if op.opcode == 0x3E:  # if opcode == 'LD A,(0x0 ~ 0xFF)'
            return op.optional_arg

    raise Exception('~~ Warning: Could not resolve new bank adress! ~~')


def calculate_internal_address(pc, bank):
    if pc < 0x4000:
        return pc

    else:
        return (bank << 16) | pc


def get_real_address(internal_address):
    return internal_address & 0xFFFF


def get_bank_num(internal_address):
    return internal_address >> 16


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

    return '\nCould not resolve HL value!'


def merge_chunks(chunk1: [Opcode], chunk2: [Opcode]):
    s1, s2 = chunk1[0].address, chunk2[0].address

    if s1 < s2:
        cross_point = chunk1.index(s2)
        return chunk1[0:cross_point] + chunk2

    elif s1 > s2:
        cross_point = chunk2.index(s1)
        return chunk2[0:cross_point] + chunk1

    else:
        return chunk1


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
    chunk_start = calculate_internal_address(pc, bank)
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
                op.warning = e.args[0]

        chunk_opcodes.append(op)

        if op.opcode in PUSH_FAMILY:
            if stack_balance < 0:
                op.warning = 'Overwriting previous stack frame!'

            stack_balance += 1

        elif op.opcode in POP_FAMILY:
            if stack_balance <= 0:
                op.warning = 'Popped additional stack frame!'

            stack_balance -= 1

        if op.opcode in split_op:
            split_dst = op.optional_arg

            if op.opcode in JR_COND_FAMILY:
                split_dst = pc + u8_correction(split_dst) + 2

            if calculate_internal_address(split_dst, bank) not in visited_chunks and split_dst < 0x8000:
                if op.opcode in CALL_FAMILY:
                    visit_que.append((split_dst, bank, [], 0))

                else:
                    visit_que.append((split_dst, bank, stack.copy(), stack_balance))

        if op.opcode in end_op:
            ending = True

            if op.opcode in JUMP_FAMILY:
                next_addr = op.optional_arg

                if op.opcode == 0x18:
                    next_addr = pc + u8_correction(next_addr) + 2  # JR length is always 2

            elif op.opcode == 0xE9:
                next_addr = get_hl_mod(chunk_opcodes)

            else:
                if stack_balance < 0:
                    next_addr = 'Detected stack manipulation: chunk pops return address!'

                elif stack_balance > 0:
                    next_addr = 'Detected stack manipulation: chunk pushes new return address!'

                elif len(stack) > 0:
                    next_addr, stack_balance = stack.pop()

                else:
                    next_addr = ''

        pc += op.opcode_len

    chunk_end = calculate_internal_address(pc - 1, bank)

    return Rang(chunk_start, chunk_end), chunk_opcodes, next_addr, bank, stack_balance


def follow_path(data, pc, bank, visited_chunks, visit_que, stack, stack_balance, max_depth):
    depth = 0

    while depth < max_depth:
        if pc >= 0x4000 and isinstance(bank, str):
            print('Error: bank changed in runtime!')
            break

        if calculate_internal_address(pc, bank) not in visited_chunks:
            chunk_range, op_list, pc, bank, stack_balance = get_chunk(pc, data, bank, stack, stack_balance, visit_que, visited_chunks)
            depth += 1

            if chunk_range.end in visited_chunks:
                old = visited_chunks[chunk_range.end]
                new = merge_chunks(op_list, old)
                visited_chunks.remove(chunk_range.end)
                visited_chunks.insert(Rang(new[0].address, new[-1].address), new)

            else:
                visited_chunks.insert(chunk_range, op_list)

            if isinstance(pc, str):
                print(pc + '\n')
                break

            elif pc >= 0x8000:
                print('Dynamic Execution: program go out of ROM!\n')
                break

        else:
            break


def print_opcodes(opcode_list):
    start_addr = opcode_list[0].address
    bank_str = '' if start_addr < 0x4000 else ' (BANK 0x{:X})'.format(get_bank_num(start_addr))
    fmt_str = '0x{0:X} {1}{2}'
    header = '----- CHUNK 0x{0:X}{1} -----'.format(get_real_address(start_addr), bank_str)
    footer = '-' * len(header) + '\n'

    warning_str = '\t\t[{}]'

    print(header)

    for op in opcode_list:
        warning = warning_str.format(op.warning) if op.warning is not None else ''
        real_address = get_real_address(op.address)

        if op.opcode <= 0xFF:
            tmp_op = opcodes[op.opcode]

            if op.optional_arg is not None:
                tmp_op = tmp_op.format(op.optional_arg)

            print(fmt_str.format(real_address, tmp_op, warning))

        else:
            print(fmt_str.format(real_address, ext_opcodes[op.opcode - 0xCB00], warning))

    print(footer)


binary = []
chunks = bintrees.RBTree()
visit_queue = [(int(sys.argv[2], 16), 1, [], 0)]  # (pc, bank, stack, stack_balance)

with open(sys.argv[1], 'rb') as file:
    binary = file.read()

while len(visit_queue) > 0:
    next_path = visit_queue.pop()
    follow_path(binary, next_path[0], next_path[1], chunks, visit_queue, next_path[2], next_path[3], int(sys.argv[3]))

for i in chunks:
    print_opcodes(chunks[i])

