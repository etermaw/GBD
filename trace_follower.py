import bintrees
from opcodes import *
from helpers import *
from dispatcher import *

# opcode families
PUSH_FAMILY = {0xC5, 0xD5, 0xE5, 0xF5}
POP_FAMILY = {0xC1, 0xD1, 0xE1, 0xF1}
RST_FAMILY = {0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF}
JUMP_FAMILY = {0x18, 0xC3}
RET_FAMILY = {0xC9, 0xD9}

JR_COND_FAMILY = {0x20, 0x28, 0x30, 0x38}
RET_COND_FAMILY = {0xC0, 0xC8, 0xD0, 0xD8}
JP_COND_FAMILY = {0xC2, 0xCA, 0xD2, 0xDA}
CALL_FAMILY = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC}
CALL_RST_FAMILY = CALL_FAMILY | RST_FAMILY

# opcodes that ends chunk
#       JP(HL)
end_op = {0xE9} | JUMP_FAMILY | RET_FAMILY

# opcodes that causes split in path
split_op = JR_COND_FAMILY | JP_COND_FAMILY | CALL_FAMILY | RST_FAMILY


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
        optional_arg = None
        op_length = op_len[opcode]

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
        ending = False
        chunk_opcodes = []
        next_addr = None
        error_end = None

        while not ending:
            op = self.get_single_op(pc, bank)

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

                elif op.opcode in RST_FAMILY:
                    split_dst = ((op.opcode >> 3) & 7) * 0x8

                if calculate_internal_address(split_dst, bank) not in self.chunk_cache and split_dst < 0x8000:
                    if op.opcode in CALL_RST_FAMILY:
                        self.visit_queue.append((split_dst, bank, 0))  # TODO: suspend current path, trace this function

                    else:
                        self.visit_queue.append((split_dst, bank, stack_balance))

            if op.opcode in end_op:
                ending = True

                if op.opcode in JUMP_FAMILY:
                    next_addr = op.optional_arg

                    if op.opcode == 0x18:
                        next_addr = pc + u8_correction(next_addr) + 2  # JR length is always 2

                elif op.opcode == 0xE9:
                    error_end, next_addr = get_hl_mod(chunk_opcodes)

                else:
                    if stack_balance < 0:
                        error_end = 'Detected stack manipulation: chunk pops return address!'

                    elif stack_balance > 0:
                        error_end = 'Detected stack manipulation: chunk pushes new return address!'

            pc += op.opcode_len

        chunk_end = calculate_internal_address(pc - 1, bank)

        if next_addr is not None and next_addr >= 0x8000:
            error_end = 'Dynamic Execution: program go out of ROM!'

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
