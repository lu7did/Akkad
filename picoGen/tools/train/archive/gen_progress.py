"""Single-physical-line Unicode training progress with per-generation summaries.

No genetic operators or scoring live in this module.
"""
import math
import shutil
import sys
import time


class TrainingProgress:
    def __init__(self, label, positions, population=1, generations=1, *, stream=None,
                 clock=None, interval=0.25):
        self.label = label[:8]
        self.positions = int(positions)
        self.population = int(population)
        self.generations = int(generations)
        self.total = self.positions * self.population * self.generations
        self.stream = stream if stream is not None else sys.stdout
        self.clock = clock if clock is not None else time.monotonic
        self.interval = interval
        self.start = self.clock()
        self.last_draw = float('-inf')
        self.last_length = 0
        self.tty = bool(getattr(self.stream, 'isatty', lambda: False)())
        self.last_done = -1
        self.error_min = None
        self.error_mean = None
        self.active = False
        self.ended = False

    @staticmethod
    def _eta(seconds):
        if seconds is None or not math.isfinite(seconds):
            return '----:--:--'
        n = max(0, int(seconds))
        return f'{min(9999, n // 3600):04d}:{(n // 60) % 60:02d}:{n % 60:02d}'

    def set_errors(self, minimum, mean):
        self.error_min = float(minimum)
        self.error_mean = float(mean)

    def reset_errors(self):
        self.error_min = None
        self.error_mean = None

    def _render(self, done, now):
        done = max(0, min(self.total, int(done)))
        fraction = 1.0 if not self.total else done / self.total
        elapsed = max(0.0, now - self.start)
        eta = None if done <= 0 else elapsed * (self.total - done) / done
        pw = len(str(max(1, self.positions)))
        iw = len(str(max(1, self.population)))
        gw = len(str(max(1, self.generations)))
        ipos = (done - 1) % self.positions + 1 if done and self.positions else 0
        ind = ((done - 1) // self.positions) % self.population + 1 if done and self.positions else 0
        gen = (done - 1) // (self.positions * self.population) + 1 if done and self.positions else 0
        if self.error_min is None:
            minimum = '   --'
            mean = '      --'
        else:
            minimum = f'{self.error_min:6.2f}' if self.error_min != int(self.error_min) else f'{self.error_min:6.0f}'
            mean = f'{self.error_mean:8.2f}'
        pct = f'{100*fraction:6.2f}%'
        pos = f'{ipos:>{pw}}/{self.positions:>{pw}}'
        stats = f' min={minimum} avg={mean}' if self.population > 1 else ''
        short_stats = f' e={minimum}/{mean.strip()}' if self.population > 1 else ''
        columns = max(20, shutil.get_terminal_size((80,24)).columns)
        cap = columns - 2
        # First preserve the fields the user needs (percent, positions,
        # minimum/mean error). Drop secondary fields when necessary.
        gen_field = f' g={gen:>{gw}}/{self.generations:>{gw}}'
        short_gen = f' g={gen:>{gw}}'
        candidates = [
            f' {pct} pos={pos}{gen_field} i={ind:>{iw}}/{self.population:>{iw}}{stats} ETA={self._eta(eta)}',
            f' {pct} pos={pos}{gen_field}{stats} ETA={self._eta(eta)}',
            f' {pct} pos={pos}{short_gen}{stats} ETA={self._eta(eta)}',
            f' {pct} pos={pos}{gen_field}{stats}',
            f' {pct} pos={pos}{short_gen}{stats}',
            f' {pct} pos={pos}{stats} ETA={self._eta(eta)}',
            f' {pct} pos={pos}{stats}',
            f' {pct} p={pos}{short_gen}{short_stats}',
            f' {pct} p={pos}{short_stats}',
            f' {pct} {pos}{short_stats}',
            f' {pct} {pos}',
            f' {pct}',
        ]
        # Reserve room for at least two visible Unicode blocks on narrow consoles.
        suffix = next((c for c in candidates if len(self.label) + 6 + len(c) <= cap), candidates[-1])
        bar_width = max(0, min(24, cap - (len(self.label) + 3 + len(suffix))))
        filled = int(bar_width * fraction)
        bar = '[' + '█' * filled + '░' * (bar_width-filled) + ']' if bar_width else ''
        line = f'{self.label} {bar}{suffix}'
        return line[:cap]

    def update(self, done, *, force=False, auto_end=True):
        done = max(0, min(self.total, int(done)))
        now = self.clock()
        if not force and done != self.total and now - self.last_draw < self.interval:
            return
        if not force and done == self.last_done:
            return
        if self.ended and done == self.total:
            return
        if not self.tty and done != self.total and not force:
            return
        line = self._render(done, now)
        if self.tty:
            pad = ' ' * max(0, self.last_length - len(line))
            self.stream.write('\r' + line + pad)
            self.last_length = len(line)
            self.active = True
            if done == self.total and auto_end:
                self.stream.write('\n')
                self.active = False
                self.last_length = 0
                self.ended = True
        else:
            # Buffered lines / CI: show only generation endings or explicit
            # final completion; no repeated output during individuals.
            if force or done == self.total:
                self.stream.write(line + '\n')
                if done == self.total and auto_end:
                    self.ended = True
        self.stream.flush()
        self.last_draw = now
        self.last_done = done

    def finish_generation(self, done):
        """Make a permanent line per generation and start next on a fresh row."""
        self.update(done, force=True, auto_end=False)
        if self.tty and self.active:
            self.stream.write('\n')
            self.stream.flush()
            self.active = False
            self.last_length = 0
        self.ended = done >= self.total

    def finish(self):
        if self.ended:
            return
        self.finish_generation(self.total)

    def abort(self):
        if self.tty and self.active:
            self.stream.write('\n')
            self.stream.flush()
            self.active = False
            self.last_length = 0
