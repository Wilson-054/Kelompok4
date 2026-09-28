import statistics
import sys

vals = [float(x) for x in sys.stdin.read().split()]
if len(vals) < 2:
    sys.exit("Sampel kurang dari 2, ambil log lebih banyak.")

vals.sort()
n = len(vals)
q = statistics.quantiles(vals, n=100)
under = sum(1 for v in vals if v < 5.0)

print(f"n        : {n}")
print(f"min      : {vals[0]:.4f} ms")
print(f"mean     : {statistics.mean(vals):.4f} ms")
print(f"median   : {statistics.median(vals):.4f} ms")
print(f"stdev    : {statistics.stdev(vals):.4f} ms")
print(f"p95      : {q[94]:.4f} ms")
print(f"p99      : {q[98]:.4f} ms")
print(f"max      : {vals[-1]:.4f} ms")
print(f"< 5 ms   : {under}/{n} ({100 * under / n:.2f}%)")
