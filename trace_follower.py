import bintrees
from opcodes import *
from helpers import *
from dispatcher import *


# helper functions
def u8_correction(value):
    if value > 127:
        value -= 256

    return value


def calculate_internal_address(pc, bank):
    if pc < 0x4000:
        return pc

    else:
        return (bank << 16) | pc


def merge_chunks(chunk1, chunk2):
    s1, s2 = chunk1[0].address, chunk2[0].address

    if s1 < s2:
        cross_point = chunk1.index(s2)
        return chunk1[0:cross_point] + chunk2

    elif s1 > s2:
        cross_point = chunk2.index(s1)
        return chunk2[0:cross_point] + chunk1

    else:
        return chunk1


def is_valid_pc(pc):
    return (pc is not None) and (pc < 0x8000)


class TraceFollower:
    program = []
    visit_queue = []
    chunk_cache = bintrees.RBTree()

    def __init__(self, program_data):
        self.program = program_data

    def get_byte(self, pc, bank):
        if pc < 0x4000:
            return self.program[pc]

        else:
            return self.program[(pc - 0x4000) + 0x4000 * bank]

    def get_single_op(self, pc, bank):
        opcode = self.get_byte(pc, bank)
        op_length = op_len[opcode]
        optional_arg = None

        if opcode == 0xCB:
            opcode = 0xCB00 + self.get_byte(pc + 1, bank)
            op_length = 2

        else:
            if op_length == 2:
                optional_arg = self.get_byte(pc + 1, bank)

            elif op_length == 3:
                optional_arg = (self.get_byte(pc + 2, bank) << 8) | self.get_byte(pc + 1, bank)

        return Opcode(calculate_internal_address(pc, bank), opcode, optional_arg, op_length)

    def get_chunk(self, pc, bank, stack_balance):
        chunk_start = calculate_internal_address(pc, bank)
        chunk_opcodes = []
        next_addr = None
        error_end = None

        op = self.get_single_op(pc, bank)
        chunk_opcodes.append(op)
        pc += op.opcode_len

        while op.opcode not in end_op:
            # if LD A, (0x2000 ~ 0x3FFF) [change bank command]
            if op.opcode == 0xEA and 0x2000 <= op.optional_arg <= 0x3FFF:
                try:
                    bank = get_new_bank(chunk_opcodes)

                except Exception as e:
                    op.warning = e.args[0]

            if op.opcode in PUSH_FAMILY:
                if stack_balance < 0:
                    op.warning = 'Overwriting previous stack frame!'

                stack_balance += 1

            elif op.opcode in POP_FAMILY:
                if stack_balance <= 0:
                    op.warning = 'Popped additional stack frame!'

                stack_balance -= 1

            elif op.opcode in split_op:
                split_dst = op.optional_arg

                if op.opcode in JR_COND_FAMILY:
                    split_dst = pc + u8_correction(split_dst)

                elif op.opcode in RST_FAMILY:
                    split_dst = ((op.opcode >> 3) & 7) * 0x8

                if calculate_internal_address(split_dst, bank) not in self.chunk_cache and split_dst < 0x8000:
                    if op.opcode in CALL_RST_FAMILY:
                        self.visit_queue.append((split_dst, bank, 0))  # TODO: suspend current path, trace this function

                    else:
                        self.visit_queue.append((split_dst, bank, stack_balance))

            op = self.get_single_op(pc, bank)
            chunk_opcodes.append(op)
            pc += op.opcode_len

        if op.opcode in JUMP_FAMILY:
            next_addr = op.optional_arg

            if op.opcode == 0x18:
                next_addr = pc + u8_correction(next_addr)

        elif op.opcode == 0xE9:
            error_end, next_addr = get_hl_mod(chunk_opcodes)

        else:
            if stack_balance < 0:
                error_end = 'Detected stack manipulation: chunk pops return address!'

            elif stack_balance > 0:
                error_end = 'Detected stack manipulation: chunk pushes new return address!'

        if next_addr is not None and next_addr >= 0x8000:
            error_end = 'Dynamic Execution: program go out of ROM!'

        chunk_end = calculate_internal_address(pc - 1, bank)

        return Rang(chunk_start, chunk_end), Chunk(chunk_opcodes, error_end), next_addr, bank, stack_balance

    def follow_path(self, pc, bank, stack_balance):
        while is_valid_pc(pc) and calculate_internal_address(pc, bank) not in self.chunk_cache:
            if calculate_internal_address(pc, bank) not in self.chunk_cache:
                chunk_range, chunk, pc, bank, stack_balance = self.get_chunk(pc, bank, stack_balance)

                if chunk_range.end in self.chunk_cache:
                    old = self.chunk_cache[chunk_range.end]
                    new = merge_chunks(chunk.opcodes, old.opcodes)

                    self.chunk_cache.remove(chunk_range.end)
                    chunk_range = Rang(new[0].address, new[-1].address)
                    chunk = Chunk(new, old.end_warning)

                self.chunk_cache.insert(chunk_range, chunk)

    def trace_all_paths(self, start_pc, start_bank):
        self.visit_queue.append((start_pc, start_bank, 0))

        while len(self.visit_queue) > 0:
            next_path = self.visit_queue.pop()
            self.follow_path(next_path[0], next_path[1], next_path[2])
