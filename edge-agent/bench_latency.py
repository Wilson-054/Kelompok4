import contextlib
import io
import platform
import random
import statistics
import time

BIN_HEIGHT_CM = 60.0
THRESH = 80.0
N = 100_000
WARMUP = 1_000

actuator_state = False


def distance_to_fill_pct(d):
    return round(max(0, min(100, (1 - d / BIN_HEIGHT_CM) * 100)), 1)


def actuate(is_full):
    global actuator_state
    actuator_state = is_full


def run(mode):
    out = []
    for i in range(N + WARMUP):
        d = random.uniform(5, 65)
        t1 = time.perf_counter_ns()
        is_full = distance_to_fill_pct(d) >= THRESH        # THINK
        if mode != "think":
            actuate(is_full)                               # ACT
        if mode == "think_act_print":
            print(f"[ACTUATOR-SIM] {'BUZZER ON' if is_full else 'normal'}")
        t2 = time.perf_counter_ns()
        if i >= WARMUP:
            out.append((t2 - t1) / 1e6)
    return sorted(out)


def report(name, v):
    n = len(v)
    under = sum(1 for x in v if x < 5.0)
    print(f"{name:20s} n={n} mean={statistics.mean(v):.4f} median={statistics.median(v):.4f} "
          f"p95={v[int(.95 * n)]:.4f} p99={v[int(.99 * n)]:.4f} max={v[-1]:.4f} ms  "
          f"<5ms: {100 * under / n:.3f}%")


print(f"Python {platform.python_version()} | {platform.machine()} | {platform.platform()}")
report("Think", run("think"))
report("Think + Act", run("think_act"))
with contextlib.redirect_stdout(io.StringIO()):
    v = run("think_act_print")
report("Think+Act+print(*)", v)
print("(*) print diarahkan ke memori, bukan terminal sungguhan; terminal lebih lambat lagi.")
