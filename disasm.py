import sys
import colorama
from opcode_printer import print_opcodes
from trace_follower import TraceFollower


def main():
    if 2 <= len(sys.argv) <= 5:
        file_name = sys.argv[1]
        start_pc = int(sys.argv[2], 16) if len(sys.argv) >= 3 else 0x100
        start_bank = int(sys.argv[3], 16) if len(sys.argv) >= 4 else 1
        depth = int(sys.argv[4]) if len(sys.argv) == 5 else 999999999

        with open(file_name, 'rb') as file:
            binary = file.read()

        deasm = TraceFollower(binary)
        deasm.trace_all_paths(start_pc, start_bank, depth)

        for i in deasm.chunk_cache:
            print_opcodes(deasm.chunk_cache[i])

    else:
        print("Args: <program name> <start pc [hex, default: 0x100]> <ROM bank [hex, default 1]> <depth [default: inf]>")


if __name__ == "__main__":
    colorama.init(autoreset=True, convert=False, strip=False)  # remove last 2 args if not using PyCharm
    main()
    colorama.deinit()



