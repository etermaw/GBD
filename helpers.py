
class Rang:
    start = 0
    end = 0

    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __eq__(self, other):
        return other >= self.start and other <= self.end

    def __lt__(self, other):
        return self.start < other

    def __le__(self, other):
        return self.start <= other

    def __gt__(self, other):
        return self.end > other

    def __ge__(self, other):
        return self.end >= other

    def overlaps(self, other_rang):
        return self.start <= other_rang.end and self.end >= other_rang.start


class Opcode:
    address = 0
    opcode = 0
    optional_arg = 0
    opcode_len = 0

    def __init__(self, address, opcode, optional_arg, opcode_len):
        self.address = address
        self.opcode = opcode
        self.optional_arg = optional_arg
        self.opcode_len = opcode_len

    def __eq__(self, other):
        return self.address == other
