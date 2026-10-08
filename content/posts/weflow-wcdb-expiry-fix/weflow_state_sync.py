"""Windows x64 / exact WeFlow DLL only. No DLL calls, keys, or database access.

Default: read-only inspection. --apply: back up and synchronize only a stale
registry replica through the actual WeFlow process's existing user-root handle.
DPAPI and metadata checks do not replace WeFlow's native HMAC validation.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import uuid

EXPECTED_DLL = '0193625007c14fd7f95e882750e78fb9e47267a5a743dbaf95601aa373a23992'
REG_PATH = r'Software\WeFlow\Runtime'
MAGIC = 0x57464C4F57475436
ENTROPY = struct.pack('<6I', 0x33a41977, 0x920d58e1, 0xf02ec76b,
                      0xdd138a45, 0xb871249c, 0x3dea065f)

class Stop(Exception):
    pass

def require(condition, message):
    if not condition:
        raise Stop(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class Meta:
    header: bytes
    epoch: int
    fingerprint: bytes
    timestamp: int
    counter: int

def parse_record(plain):
    require(len(plain) == 88, '记录长度不适用；停止。')
    require(struct.unpack_from('<Q', plain)[0] == MAGIC and
            struct.unpack_from('<I', plain, 8)[0] == 6,
            '记录格式不适用；停止。')
    stamp, counter, epoch = struct.unpack_from('<3Q', plain, 16)
    return Meta(bytes(plain[:16]), epoch, bytes(plain[40:56]), stamp, counter)

def decide(new, old, new_meta, old_meta, context_epoch, fingerprint, now):
    require(new_meta.epoch == context_epoch and new_meta.fingerprint == fingerprint,
            '文件状态与当前 WeFlow 设备/构建上下文不匹配；停止。')
    require((new_meta.header, new_meta.epoch, new_meta.fingerprint) ==
            (old_meta.header, old_meta.epoch, old_meta.fingerprint),
            '文件与注册表版本、设备或构建不同；停止。')
    require(new_meta.timestamp <= now + 300, '文件时间超过当前时间允许范围；停止。')
    require(new_meta.timestamp >= old_meta.timestamp and new_meta.counter >= old_meta.counter,
            '同步会使时间或计数倒退；停止。')
    if new == old:
        return '一致，无需同步'
    require((new_meta.timestamp, new_meta.counter) != (old_meta.timestamp, old_meta.counter),
            '时间/计数相同但加密内容不同，无法判断来源；停止。')
    return '注册表副本较旧，可备份后同步'

class Blob(C.Structure):
    _fields_ = [('length', W.DWORD), ('data', C.POINTER(C.c_ubyte))]

class HandleEntry(C.Structure):
    _fields_ = [('object', C.c_void_p), ('pid', C.c_size_t), ('handle', C.c_size_t),
                ('access', W.ULONG), ('trace', W.USHORT), ('type', W.USHORT),
                ('attributes', W.ULONG), ('reserved', W.ULONG)]

class UnicodeString(C.Structure):
    _fields_ = [('length', W.USHORT), ('capacity', W.USHORT), ('buffer', C.c_void_p)]

class ProcessEntry(C.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD),
                ('heap', C.c_size_t), ('module', W.DWORD), ('threads', W.DWORD),
                ('parent', W.DWORD), ('priority', W.LONG), ('flags', W.DWORD),
                ('exe', W.WCHAR * 260)]

class Windows:
    def __init__(self):
        require(os.name == 'nt' and C.sizeof(C.c_void_p) == 8,
                '请使用 Windows x64 的 64 位 Python。')
        import winreg
        self.reg = winreg
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.nt = C.WinDLL('ntdll')
        self.ps = C.WinDLL('psapi', use_last_error=True)
        self.adv = C.WinDLL('advapi32', use_last_error=True)
        self.crypt = C.WinDLL('crypt32', use_last_error=True)
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = C.c_void_p
        self.k.CloseHandle.argtypes = [C.c_void_p]
        self.k.GetCurrentProcess.restype = C.c_void_p
        self.k.LocalFree.argtypes = [C.c_void_p]
        self.k.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
        self.k.CreateToolhelp32Snapshot.restype = C.c_void_p
        self.k.Process32FirstW.argtypes = [C.c_void_p, C.POINTER(ProcessEntry)]
        self.k.Process32NextW.argtypes = [C.c_void_p, C.POINTER(ProcessEntry)]
        self.k.DuplicateHandle.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p,
                                           C.POINTER(C.c_void_p), W.DWORD, W.BOOL, W.DWORD]
        self.k.ReadProcessMemory.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p,
                                            C.c_size_t, C.POINTER(C.c_size_t)]
        self.ps.EnumProcessModulesEx.argtypes = [C.c_void_p, C.POINTER(C.c_void_p),
                                                 W.DWORD, C.POINTER(W.DWORD), W.DWORD]
        self.ps.GetModuleFileNameExW.argtypes = [C.c_void_p, C.c_void_p, W.LPWSTR, W.DWORD]
        self.adv.OpenProcessToken.argtypes = [C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)]
        self.adv.GetTokenInformation.argtypes = [C.c_void_p, C.c_int, C.c_void_p,
                                                W.DWORD, C.POINTER(W.DWORD)]
        self.adv.ConvertSidToStringSidW.argtypes = [C.c_void_p, C.POINTER(C.c_void_p)]
        self.nt.NtQuerySystemInformation.argtypes = [W.ULONG, C.c_void_p, W.ULONG,
                                                    C.POINTER(W.ULONG)]
        self.nt.NtQuerySystemInformation.restype = C.c_long
        self.nt.NtQueryObject.argtypes = [C.c_void_p, W.ULONG, C.c_void_p, W.ULONG,
                                        C.POINTER(W.ULONG)]
        self.nt.NtQueryObject.restype = C.c_long
        self.crypt.CryptUnprotectData.argtypes = [C.POINTER(Blob), C.c_void_p,
            C.POINTER(Blob), C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(Blob)]

    def sid(self, process):
        token = C.c_void_p()
        require(self.adv.OpenProcessToken(process, 8, C.byref(token)), '无法查询进程账号。')
        try:
            buf = C.create_string_buffer(4096)
            size = W.DWORD()
            require(self.adv.GetTokenInformation(token, 1, buf, len(buf), C.byref(size)),
                    '无法查询进程 SID。')
            sid_ptr = C.c_void_p.from_buffer(buf).value
            text_ptr = C.c_void_p()
            require(self.adv.ConvertSidToStringSidW(sid_ptr, C.byref(text_ptr)), 'SID 转换失败。')
            try:
                return C.wstring_at(text_ptr.value)
            finally:
                self.k.LocalFree(text_ptr)
        finally:
            self.k.CloseHandle(token)

    def processes(self):
        snap = self.k.CreateToolhelp32Snapshot(2, 0)
        require(snap and snap != C.c_void_p(-1).value, '无法列出进程。')
        try:
            entry = ProcessEntry()
            entry.size = C.sizeof(entry)
            ok = self.k.Process32FirstW(snap, C.byref(entry))
            while ok:
                if entry.exe.lower() == 'weflow.exe':
                    yield entry.pid
                ok = self.k.Process32NextW(snap, C.byref(entry))
        finally:
            self.k.CloseHandle(snap)

    def modules(self, process):
        modules = (C.c_void_p * 4096)()
        needed = W.DWORD()
        require(self.ps.EnumProcessModulesEx(process, modules, C.sizeof(modules),
                                             C.byref(needed), 3), '无法查看 WeFlow 模块。')
        require(needed.value <= C.sizeof(modules), '模块数量超过检查范围。')
        result = []
        for base in modules[:needed.value // 8]:
            name = C.create_unicode_buffer(32768)
            require(self.ps.GetModuleFileNameExW(process, base, name, len(name)),
                    '无法确定模块路径。')
            result.append((base, Path(name.value)))
        return result

    def choose_process(self, requested):
        matches = []
        for pid in self.processes():
            if requested and pid != requested:
                continue
            process = self.k.OpenProcess(0x450, False, pid)
            if not process:
                continue
            try:
                native = [(base, path) for base, path in self.modules(process)
                          if path.name.lower() == 'wcdb_api.dll']
                if len(native) == 1:
                    matches.append((pid, process, *native[0]))
                    process = None
            except Stop:
                pass
            finally:
                if process:
                    self.k.CloseHandle(process)
        if len(matches) != 1:
            for _, process, _, _ in matches:
                self.k.CloseHandle(process)
            raise Stop('无法唯一找到加载 DLL 的 WeFlow。请正常打开报错窗口并保持运行；关闭其他 WeFlow 副本。')
        return matches[0]

    def read(self, process, address, length):
        buf = C.create_string_buffer(length)
        done = C.c_size_t()
        require(self.k.ReadProcessMemory(process, address, buf, length, C.byref(done))
                and done.value == length, '无法读取非秘密的组件状态字段。')
        return buf.raw

    def decrypt_meta(self, data):
        require(0 < len(data) <= 65536, '加密状态长度异常。')
        buf = (C.c_ubyte * len(data)).from_buffer_copy(data)
        eb = (C.c_ubyte * len(ENTROPY)).from_buffer_copy(ENTROPY)
        source, entropy, out = Blob(len(data), buf), Blob(len(ENTROPY), eb), Blob()
        require(self.crypt.CryptUnprotectData(C.byref(source), None, C.byref(entropy),
                                              None, None, 1, C.byref(out)),
                'DPAPI 解密失败。脚本不适用于当前状态，不会同步。')
        plain = bytearray()
        try:
            plain = bytearray(C.string_at(out.data, out.length))
            return parse_record(plain)
        finally:
            for i in range(len(plain)):
                plain[i] = 0
            C.memset(out.data, 0, out.length)
            self.k.LocalFree(out.data)

    def object_text(self, handle, kind):
        buf = C.create_string_buffer(16384)
        size = W.ULONG()
        if self.nt.NtQueryObject(handle, kind, buf, len(buf), C.byref(size)) < 0:
            return None
        value = UnicodeString.from_buffer(buf)
        return C.wstring_at(value.buffer, value.length // 2) if value.buffer else ''

    def roots(self, process, pid, sid):
        size = 1024 * 1024
        while True:
            buf = C.create_string_buffer(size)
            needed = W.ULONG()
            result = self.nt.NtQuerySystemInformation(64, buf, size, C.byref(needed))
            if result >= 0:
                break
            require(result == -1073741820 and size < 256 * 1024 * 1024,
                    '无法列出注册表句柄；当前 Windows 版本或权限不适用。')
            size = max(size * 2, needed.value + 65536)
        count = C.c_size_t.from_buffer(buf).value
        require(16 + count * C.sizeof(HandleEntry) <= len(buf), '句柄数据长度异常。')
        root_name = '\\REGISTRY\\USER\\' + sid
        for i in range(count):
            entry = HandleEntry.from_buffer(buf, 16 + i * C.sizeof(HandleEntry))
            if entry.pid != pid:
                continue
            duplicate = C.c_void_p()
            if not self.k.DuplicateHandle(process, entry.handle, self.k.GetCurrentProcess(),
                                          C.byref(duplicate), 0, False, 2):
                continue
            try:
                if self.object_text(duplicate, 2) == 'Key' and self.object_text(duplicate, 1) == root_name:
                    yield duplicate.value
            finally:
                self.k.CloseHandle(duplicate)

    def get_value(self, root, name):
        with self.reg.OpenKey(root, REG_PATH) as key:
            value, kind = self.reg.QueryValueEx(key, name)
        require(kind == self.reg.REG_BINARY, '注册表状态类型不是 REG_BINARY。')
        return value

    def set_value(self, root, name, old, new):
        with self.reg.OpenKey(root, REG_PATH, 0, self.reg.KEY_READ | self.reg.KEY_SET_VALUE) as key:
            require(self.reg.QueryValueEx(key, name)[0] == old,
                    '注册表值在检查后发生变化；停止，不覆盖。')
            self.reg.SetValueEx(key, name, 0, self.reg.REG_BINARY, new)
            self.reg.FlushKey(key)
            require(self.reg.QueryValueEx(key, name)[0] == new, '写入后核验失败，保留备份。')

def find_files(local):
    state = local / 'WeFlow' / 'State'
    pairs = []
    for path in state.glob('native-anchor-v7-*.bin'):
        match = re.fullmatch(r'native-anchor-v7-(e1c84b9f06d1237a-[0-9a-f]{16})\.bin', path.name)
        if match:
            other = local / 'WeFlow' / 'Runtime' / ('anchor-v7-' + match[1] + '.bin')
            if other.is_file():
                pairs.append((path, other, 'AnchorV7-' + match[1]))
    require(len(pairs) == 1, '无法唯一确定本版本的两份状态文件；停止，不猜测或创建状态。')
    return pairs[0]

def synchronize(api, root, name, files, old, new, backup_parent):
    require(all(path.read_bytes() == new for path in files), '文件在检查后变化；停止。')
    require(api.get_value(root, name) == old, '注册表在检查后变化；停止。')
    backup = backup_parent / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, exist_ok=False)
    (backup / 'registry-before.bin').write_bytes(old)
    (backup / 'State-before.bin').write_bytes(new)
    (backup / 'Runtime-before.bin').write_bytes(new)
    info = {'version': 1, 'state_files': [str(path) for path in files],
            'registry_path': REG_PATH, 'registry_name': name,
            'old_registry_sha256': sha(old), 'new_sha256': sha(new),
            'operation': 'prepared', 'note': 'encrypted local backups; do not publish'}
    manifest = backup / 'manifest.json'
    manifest.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    require(all(path.read_bytes() == new for path in files), '备份后文件已变化；未同步。')
    api.set_value(root, name, old, new)
    info['operation'] = 'applied'
    manifest.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    return backup

def main():
    parser = argparse.ArgumentParser(description='WeFlow 6.3.1 指定补丁：实际注册表视图状态同步；默认只读。')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='只检查（默认）')
    mode.add_argument('--apply', action='store_true', help='检查、备份后同步较旧的注册表副本')
    parser.add_argument('--pid', type=int, help='可选：指定加载 DLL 的 WeFlow 进程')
    args = parser.parse_args()
    api = Windows()
    pid, process, base, dll_path = api.choose_process(args.pid)
    try:
        require(sha(dll_path.read_bytes()) == EXPECTED_DLL,
                'DLL 哈希不匹配。此脚本只适用于文章指定的 6.3.1 补丁。')
        sid = api.sid(process)
        require(sid == api.sid(api.k.GetCurrentProcess()), '请使用运行 WeFlow 的同一 Windows 账号。')
        local = Path(os.environ['LOCALAPPDATA'])
        first, second, name = find_files(local)
        new = first.read_bytes()
        require(new == second.read_bytes(), '两份文件不一致；无法判断正确副本，不会同步。')
        require(struct.unpack('<I', api.read(process, base + 0x18cbd0, 4))[0] == 2,
                'WeFlow 设备上下文尚未初始化；停止。')
        epoch = struct.unpack('<Q', api.read(process, base + 0x18cbd8, 8))[0]
        fingerprint = api.read(process, base + 0x18cc38, 16)
        loaded = bool(api.read(process, base + 0x18cbc1, 1)[0])
        new_meta = api.decrypt_meta(new)
        roots = api.roots(process, pid, sid)
        chosen = None
        values = []
        # Hold duplicated handles until checks finish; refuse conflicting views.
        retained = []
        try:
            for root in roots:
                try:
                    old = api.get_value(root, name)
                except OSError:
                    continue
                duplicate = C.c_void_p()
                require(api.k.DuplicateHandle(api.k.GetCurrentProcess(), root, api.k.GetCurrentProcess(),
                                               C.byref(duplicate), 0, False, 2), '保留根句柄失败。')
                retained.append(duplicate.value)
                values.append(old)
                if chosen is None:
                    chosen = duplicate.value
            require(chosen is not None, '未找到 WeFlow 实际用户根中的对应状态，不会回退到脚本自身 HKCU。')
            require(all(value == values[0] for value in values), '进程内多个视图不一致；停止。')
            old = values[0]
            old_meta = api.decrypt_meta(old)
            decision = decide(new, old, new_meta, old_meta, epoch, fingerprint, int(time.time()))
            report = {'pid': pid, 'dll_sha256': EXPECTED_DLL, 'decision': decision,
                      'native_state_loaded': loaded,
                      'file_sha256': sha(new), 'actual_registry_sha256': sha(old),
                      'file_time_counter': [new_meta.timestamp, new_meta.counter],
                      'registry_time_counter': [old_meta.timestamp, old_meta.counter],
                      'native_hmac_checked_by_script': False}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if new == old:
                print('实际三份副本一致，未修改。若仍报 -105，请继续排查其他原因。')
                return 0
            require(not loaded, 'WeFlow 已加载状态，可能正在正常更新；不会在运行成功时修改。')
            if not args.apply:
                print('只读检查完成，未写入。确定属于文中的 -105 后，可执行 --apply。')
                return 0
            require(not bool(api.read(process, base + 0x18cbc1, 1)[0]), '应用状态已变化；停止。')
            backup = synchronize(api, chosen, name, (first, second), old, new,
                                 Path(__file__).resolve().parent / 'weflow-state-backups')
            print('同步完成；加密备份：' + str(backup))
            print('请通过托盘退出 WeFlow 后重开，再退出重开一次。最终 HMAC 校验与结果由真实 WeFlow 启动确认。')
            print('若仍失败，请保留备份；不要删除状态或把本机备份上传博客。')
            return 0
        finally:
            roots.close()
            for root in retained:
                api.k.CloseHandle(root)
    finally:
        api.k.CloseHandle(process)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Stop, OSError, KeyError) as error:
        print('停止：' + str(error), file=sys.stderr)
        sys.exit(2)
