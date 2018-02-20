import sys
import colorama
from opcode_printer import print_opcodes
from trace_follower import TraceFollower


def main():
    if 2 <= len(sys.argv) <= 4:
        file_name = sys.argv[1]
        start_pc = int(sys.argv[2], 16) if len(sys.argv) >= 3 else 0x100
        start_bank = int(sys.argv[3], 16) if len(sys.argv) >= 4 else 1

        try:
            with open(file_name, 'rb') as file:
                binary = file.read()

            deasm = TraceFollower(binary)
            deasm.trace_all_paths(start_pc, start_bank)

            for i in deasm.chunk_cache:
                print_opcodes(deasm.chunk_cache[i])

        except FileNotFoundError:
            print("ERROR: File not found!")

    else:
        print("Args: <program name> <start pc [hex, default: 0x100]> <ROM bank [hex, default 1]>")


if __name__ == "__main__":
    colorama.init(autoreset=True, convert=False, strip=False)  # remove last 2 args if not using PyCharm
    main()
    colorama.deinit()



