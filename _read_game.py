import sys
fname = sys.argv[1]
start = int(sys.argv[2])
end = int(sys.argv[3])
with open(fname, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if start <= i <= end:
            print(f'{i}: {line}', end='')
