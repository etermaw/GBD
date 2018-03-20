from helpers import Opcode
from opcodes import *


def calculate_internal_address(pc, bank):
    if pc < 0x4000:
        return pc

    else:
        return (bank << 16) | pc


class Chunker:
    program = None

    def __init__(self, program):
        self.program = program

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

    def get_raw_chunk(self, pc, bank):
        chunk_opcodes = []

        op = self.get_single_op(pc, bank)
        chunk_opcodes.append(op)
        pc += op.opcode_len

        while op.opcode not in end_op:
            op = self.get_single_op(pc, bank)
            chunk_opcodes.append(op)
            pc += op.opcode_len

        return chunk_opcodes, pc  # chunk range can be easily calculated from returned pc
