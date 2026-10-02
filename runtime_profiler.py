import json
import os
import sys
import threading
import time
from collections import Counter
from pathlib import Path

SIM_FILES = {
    'engine.py',
    'learning_engine.py',
    'weather_engine.py',
    'weather_control_engine.py',
    'hot_mechanics_engine.py',
}


class RuntimeSampler:
    """Low-overhead statistical profiler for the simulation thread(s).

    It samples Python stacks instead of instrumenting every call, so the
    simulation semantics and timing are not materially changed. Only frames
    belonging to SIM.lab engine modules are counted.
    """

    def __init__(self, thread_names=None):
        self.sample_seconds = max(5.0, min(60.0, float(os.getenv('SIM_PERF_SAMPLE_SECONDS', '20'))))
        self.period_seconds = max(self.sample_seconds + 10.0, min(1800.0, float(os.getenv('SIM_PERF_SAMPLE_PERIOD', '300'))))
        self.warmup_seconds = max(10.0, min(600.0, float(os.getenv('SIM_PERF_WARMUP_SECONDS', '60'))))
        self.sample_interval = max(0.02, min(0.25, float(os.getenv('SIM_PERF_SAMPLE_INTERVAL', '0.05'))))
        self.thread_names = frozenset(thread_names or ())
        self._lock = threading.Lock()
        self._generation = 0
        self._last_started_at = None
        self._last_finished_at = None
        self._samples = 0
        self._top_leaf = []
        self._top_stacks = []
        self._active = False
        self._error = None
        self._thread = threading.Thread(target=self._run, name='simlab-runtime-profiler', daemon=True)

    def start(self):
        self._thread.start()

    @staticmethod
    def _is_sim_frame(frame):
        return Path(frame.f_code.co_filename).name in SIM_FILES

    def _target_idents(self):
        if not self.thread_names:
            return None
        return {
            thread.ident
            for thread in threading.enumerate()
            if thread.ident is not None and thread.name in self.thread_names
        }

    def _sample_once(self, leaf_counts, stack_counts):
        own_ident = threading.get_ident()
        target_idents = self._target_idents()
        for ident, frame in sys._current_frames().items():
            if ident == own_ident:
                continue
            if target_idents is not None and ident not in target_idents:
                continue
            stack = []
            current = frame
            while current is not None:
                if self._is_sim_frame(current):
                    filename = Path(current.f_code.co_filename).name
                    stack.append(f'{filename}:{current.f_code.co_name}')
                current = current.f_back
            if not stack:
                continue
            # sys._current_frames() starts at the leaf/current frame.
            leaf_counts[stack[0]] += 1
            stack_counts[' <- '.join(stack[:8])] += 1

    def _profile_window(self):
        leaf_counts = Counter()
        stack_counts = Counter()
        samples = 0
        started_wall = time.time()
        deadline = time.monotonic() + self.sample_seconds
        with self._lock:
            self._active = True
            self._last_started_at = started_wall
            self._error = None
        try:
            while time.monotonic() < deadline:
                self._sample_once(leaf_counts, stack_counts)
                samples += 1
                time.sleep(self.sample_interval)
            top_leaf = [
                {'frame': frame, 'samples': count, 'pct': round(count * 100.0 / max(1, sum(leaf_counts.values())), 1)}
                for frame, count in leaf_counts.most_common(12)
            ]
            top_stacks = [
                {'stack': stack, 'samples': count}
                for stack, count in stack_counts.most_common(8)
            ]
            with self._lock:
                self._generation += 1
                self._samples = samples
                self._top_leaf = top_leaf
                self._top_stacks = top_stacks
                self._last_finished_at = time.time()
            print(json.dumps({
                'event': 'simlab_perf_sample',
                'generation': self._generation,
                'windowSeconds': self.sample_seconds,
                'samples': samples,
                'topLeaf': top_leaf,
                'topStacks': top_stacks,
            }, ensure_ascii=False, separators=(',', ':')), flush=True)
        except Exception as exc:
            with self._lock:
                self._error = f'{type(exc).__name__}: {exc}'
        finally:
            with self._lock:
                self._active = False

    def _run(self):
        time.sleep(self.warmup_seconds)
        while True:
            started = time.monotonic()
            self._profile_window()
            elapsed = time.monotonic() - started
            time.sleep(max(1.0, self.period_seconds - elapsed))

    def status(self):
        with self._lock:
            return {
                'active': self._active,
                'generation': self._generation,
                'sampleSeconds': self.sample_seconds,
                'periodSeconds': self.period_seconds,
                'sampleIntervalMs': round(self.sample_interval * 1000),
                'threadNames': sorted(self.thread_names),
                'lastStartedAt': self._last_started_at,
                'lastFinishedAt': self._last_finished_at,
                'samples': self._samples,
                'topLeaf': list(self._top_leaf),
                'topStacks': list(self._top_stacks),
                'error': self._error,
            }
