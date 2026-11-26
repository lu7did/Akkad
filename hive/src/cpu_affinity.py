"""Best-effort disjoint logical CPU affinity for local UCI processes."""
import os
import sys
import threading


def available_cpus():
    if sys.platform.startswith('linux'):
        return sorted(os.sched_getaffinity(0))
    if sys.platform == 'win32':
        import ctypes as c
        from ctypes import wintypes as w
        k=c.WinDLL('kernel32',use_last_error=True)
        k.GetCurrentProcess.restype=w.HANDLE
        k.GetProcessAffinityMask.argtypes=[w.HANDLE,c.POINTER(c.c_size_t),c.POINTER(c.c_size_t)]
        k.GetProcessAffinityMask.restype=w.BOOL
        mask=c.c_size_t(); system=c.c_size_t()
        if not k.GetProcessAffinityMask(k.GetCurrentProcess(),c.byref(mask),c.byref(system)):
            raise c.WinError(c.get_last_error())
        return [i for i in range(c.sizeof(mask)*8) if mask.value & (1<<i)]
    raise NotImplementedError('strict process affinity unsupported on '+sys.platform)


def apply_affinity(pid, cpus):
    if sys.platform.startswith('linux'):
        # Linux affinity is per thread. Cover threads already created at launch;
        # subsequent threads inherit the affinity of their creator.
        for _ in range(3):
            before=set(os.listdir(f'/proc/{pid}/task'))
            for tid in before:
                try: os.sched_setaffinity(int(tid),cpus)
                except ProcessLookupError: pass
            after=set(os.listdir(f'/proc/{pid}/task'))
            if after <= before:
                for tid in after:
                    try:
                        if os.sched_getaffinity(int(tid)) != set(cpus):
                            raise OSError('affinity verification failed')
                    except ProcessLookupError: pass
                return
        raise OSError('threads changed during affinity setup')
    if sys.platform == 'win32':
        import ctypes as c
        from ctypes import wintypes as w
        k=c.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; k.OpenProcess.restype=w.HANDLE
        k.SetProcessAffinityMask.argtypes=[w.HANDLE,c.c_size_t]; k.SetProcessAffinityMask.restype=w.BOOL
        k.GetProcessAffinityMask.argtypes=[w.HANDLE,c.POINTER(c.c_size_t),c.POINTER(c.c_size_t)]; k.GetProcessAffinityMask.restype=w.BOOL
        k.CloseHandle.argtypes=[w.HANDLE]; k.CloseHandle.restype=w.BOOL
        h=k.OpenProcess(0x0200|0x0400,False,pid)
        if not h: raise c.WinError(c.get_last_error())
        try:
            desired=sum(1<<i for i in cpus)
            if not k.SetProcessAffinityMask(h,desired): raise c.WinError(c.get_last_error())
            mask=c.c_size_t(); system=c.c_size_t()
            if not k.GetProcessAffinityMask(h,c.byref(mask),c.byref(system)): raise c.WinError(c.get_last_error())
            if mask.value!=desired: raise OSError('affinity verification failed')
        finally: k.CloseHandle(h)
        return
    raise NotImplementedError('strict process affinity unsupported on '+sys.platform)


class Pool:
    def __init__(self):
        self.lock=threading.Lock(); self.used={}
    def reserve(self, owner, count):
        with self.lock:
            occupied={cpu for values in self.used.values() for cpu in values}
            cpus=tuple(i for i in available_cpus() if i not in occupied)[:count]
            if cpus: self.used[owner]=cpus
            return cpus
    def release(self, owner):
        with self.lock: self.used.pop(owner,None)

POOL=Pool()
