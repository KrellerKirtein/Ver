#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Delphi 版本号自动升级工具

功能：自动升级 Delphi 项目的版本号第三位 (如 10.2503.X.0 中的 X)
      同时修改 .res 文件和 .dproj 文件，保持两者同步

支持：
    1. 自动递增 (+1)
    2. 指定具体的新版本号

用法：
    python version_bumper.py <project_dir> [--build <num>] [--dry-run]

示例：
    python version_bumper.py ./10_2503_6           # 自动将版本号第三位 +1
    python version_bumper.py ./10_2503_6 --build 8 # 将版本号第三位设置为 8
    python version_bumper.py ./10_2503_6 --dry-run # 预览模式
"""

import os
import sys
import re
import struct
import shutil
import argparse
from dataclasses import dataclass
from typing import Optional, List, Tuple
from pathlib import Path


# ANSI 颜色代码
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_colored(msg: str, color: str = Colors.ENDC):
    """打印彩色文本"""
    print(f"{color}{msg}{Colors.ENDC}")


def print_info(msg: str):
    print_colored(msg, Colors.CYAN)


def print_success(msg: str):
    print_colored(msg, Colors.GREEN)


def print_warning(msg: str):
    print_colored(msg, Colors.YELLOW)


def print_error(msg: str):
    print_colored(msg, Colors.RED)


@dataclass
class VersionInfo:
    """版本信息结构: Major.Minor.Build.Release (如 10.2503.6.0)"""
    major: int
    minor: int
    build: int      # 这是我们要修改的版本号
    release: int    # 通常固定为 0
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.build}.{self.release}"
    
    @classmethod
    def from_string(cls, version_str: str) -> 'VersionInfo':
        """从字符串解析版本号"""
        parts = version_str.split('.')
        if len(parts) != 4:
            raise ValueError(f"版本号格式错误: {version_str}，期望 x.x.x.x 格式")
        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            build=int(parts[2]),
            release=int(parts[3])
        )


@dataclass
class ModificationRecord:
    """修改记录"""
    file: str       # 文件名
    location: str   # 位置描述 (偏移或行号)
    type_desc: str
    old_value: str
    new_value: str


class DprojVersionBumper:
    """Delphi .dproj 文件版本号升级器"""
    
    def __init__(self, dproj_file: str):
        self.dproj_file = os.path.abspath(dproj_file)
        self.content: str = ""
        self.modifications: List[ModificationRecord] = []
        self.current_version: Optional[VersionInfo] = None
        self.new_version: Optional[VersionInfo] = None
    
    def load(self) -> bool:
        """加载 .dproj 文件"""
        if not os.path.exists(self.dproj_file):
            print_error(f"错误: 文件不存在 - {self.dproj_file}")
            return False
        
        # 尝试不同编码读取
        for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']:
            try:
                with open(self.dproj_file, 'r', encoding=encoding) as f:
                    self.content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if not self.content:
            print_error(f"错误: 无法读取文件 - {self.dproj_file}")
            return False
        
        print_info(f"目标文件: {self.dproj_file}")
        return True
    
    def analyze(self) -> bool:
        """分析 .dproj 文件中的版本号"""
        if not self.load():
            return False
        
        # 查找 VerInfo_Release
        release_match = re.search(r'<VerInfo_Release>(\d+)</VerInfo_Release>', self.content)
        if not release_match:
            print_error("错误: 无法找到 VerInfo_Release 标签")
            return False
        
        # 查找 FileVersion
        file_version_match = re.search(r'FileVersion=(\d+\.\d+\.\d+\.\d+)', self.content)
        if not file_version_match:
            print_error("错误: 无法找到 FileVersion")
            return False
        
        version_str = file_version_match.group(1)
        self.current_version = VersionInfo.from_string(version_str)
        
        print()
        print_info("=== .dproj 版本信息 ===")
        print(f"  VerInfo_Release: {release_match.group(1)}")
        print(f"  FileVersion: {version_str}")
        
        return True
    
    def update(self, new_build: int) -> bool:
        """更新 .dproj 文件中的版本号"""
        if self.current_version is None:
            raise RuntimeError("未分析版本信息")
        
        old_build = self.current_version.build
        
        # 1. 更新 VerInfo_Release
        old_pattern = f'<VerInfo_Release>{old_build}</VerInfo_Release>'
        new_pattern = f'<VerInfo_Release>{new_build}</VerInfo_Release>'
        
        if old_pattern in self.content:
            self.content = self.content.replace(old_pattern, new_pattern)
            self.modifications.append(ModificationRecord(
                file=".dproj",
                location="VerInfo_Release",
                type_desc="VerInfo_Release 标签",
                old_value=str(old_build),
                new_value=str(new_build)
            ))
        
        # 2. 更新 VerInfo_Keys 中的 FileVersion
        old_file_ver = f"{self.current_version.major}.{self.current_version.minor}.{old_build}.{self.current_version.release}"
        new_file_ver = f"{self.current_version.major}.{self.current_version.minor}.{new_build}.{self.current_version.release}"
        
        old_ver_pattern = f'FileVersion={old_file_ver}'
        new_ver_pattern = f'FileVersion={new_file_ver}'
        
        if old_ver_pattern in self.content:
            self.content = self.content.replace(old_ver_pattern, new_ver_pattern)
            self.modifications.append(ModificationRecord(
                file=".dproj",
                location="VerInfo_Keys",
                type_desc="FileVersion 字符串",
                old_value=old_file_ver,
                new_value=new_file_ver
            ))
        
        return True
    
    def save(self, backup: bool = True) -> bool:
        """保存修改后的文件"""
        if backup:
            backup_file = f"{self.dproj_file}.bak"
            shutil.copy2(self.dproj_file, backup_file)
            print_info(f"已备份原文件到: {backup_file}")
        
        with open(self.dproj_file, 'w', encoding='utf-8') as f:
            f.write(self.content)
        
        return True

class ResVersionBumper:
    """Delphi .res 文件版本号升级器"""
    
    # VS_FIXEDFILEINFO 签名 (小端序): 0xFEEF04BD
    VS_FFI_SIGNATURE = bytes([0xBD, 0x04, 0xEF, 0xFE])
    
    def __init__(self, res_file: str):
        self.res_file = os.path.abspath(res_file)
        self.data: bytearray = bytearray()
        self.modifications: List[ModificationRecord] = []
        
        # 关键偏移位置
        self.ffi_offset: int = -1                    # VS_FIXEDFILEINFO 签名位置
        self.file_version_ls_offset: int = -1       # FileVersionLS (高16位=Build)
        self.product_version_ls_offset: int = -1    # ProductVersionLS
        self.file_version_string_offset: int = -1   # FileVersion 字符串位置
        
        # 版本信息
        self.current_version: Optional[VersionInfo] = None
        self.new_version: Optional[VersionInfo] = None
    
    def load(self) -> bool:
        """加载 .res 文件"""
        if not os.path.exists(self.res_file):
            print_error(f"错误: 文件不存在 - {self.res_file}")
            return False
        
        with open(self.res_file, 'rb') as f:
            self.data = bytearray(f.read())
        
        print_info(f"目标文件: {self.res_file}")
        print_info(f"文件大小: {len(self.data):,} 字节")
        return True
    
    def find_binary_version(self) -> bool:
        """
        查找 VS_FIXEDFILEINFO 中的二进制版本号位置
        
        VS_FIXEDFILEINFO 结构 (共 52 字节):
        - dwSignature      (4 bytes): 0xFEEF04BD
        - dwStrucVersion   (4 bytes)
        - dwFileVersionMS  (4 bytes): HIWORD=Major, LOWORD=Minor
        - dwFileVersionLS  (4 bytes): HIWORD=Build, LOWORD=Release  <-- 我们修改 Build
        - dwProductVersionMS (4 bytes)
        - dwProductVersionLS (4 bytes)
        - ...
        """
        pos = self.data.find(self.VS_FFI_SIGNATURE)
        if pos == -1:
            print_error("错误: 无法找到 VS_FIXEDFILEINFO 结构")
            return False
        
        self.ffi_offset = pos
        
        # 计算各字段偏移
        # FileVersionLS 在签名后 8 字节 (跳过 signature + strucVersion + FileVersionMS)
        self.file_version_ls_offset = pos + 4 + 4 + 4
        # ProductVersionLS 在 FileVersionLS 后 8 字节
        self.product_version_ls_offset = self.file_version_ls_offset + 4 + 4
        
        # 读取当前版本号
        file_ver_ms = struct.unpack_from('<I', self.data, pos + 4 + 4)[0]
        file_ver_ls = struct.unpack_from('<I', self.data, self.file_version_ls_offset)[0]
        
        major = (file_ver_ms >> 16) & 0xFFFF
        minor = file_ver_ms & 0xFFFF
        build = (file_ver_ls >> 16) & 0xFFFF   # 高16位是 Build
        release = file_ver_ls & 0xFFFF          # 低16位是 Release
        
        print()
        print_info("=== 二进制版本信息 (VS_FIXEDFILEINFO) ===")
        print(f"  签名位置: 0x{pos:X}")
        print(f"  FileVersionLS 偏移: 0x{self.file_version_ls_offset:X}")
        print(f"  二进制版本: {major}.{minor}.{build}.{release}")
        
        return True
    
    def find_string_version(self) -> bool:
        """查找 FileVersion 字符串版本号"""
        # 搜索 "FileVersion" Unicode 字符串
        file_version_unicode = "FileVersion".encode('utf-16-le')
        pos = self.data.find(file_version_unicode)
        
        if pos == -1:
            print_error("错误: 无法找到 FileVersion 字符串")
            return False
        
        # FileVersion 后跟 null terminator，然后是版本值字符串
        search_start = pos + len(file_version_unicode) + 2
        
        # 跳过填充字节
        while search_start < len(self.data) and self.data[search_start] == 0:
            search_start += 1
        
        self.file_version_string_offset = search_start
        
        # 读取版本字符串
        version_chars = []
        i = search_start
        while i < len(self.data) - 1:
            char_code = struct.unpack_from('<H', self.data, i)[0]
            if char_code == 0:
                break
            version_chars.append(chr(char_code))
            i += 2
        
        version_string = ''.join(version_chars)
        self.current_version = VersionInfo.from_string(version_string)
        
        print()
        print_info("=== 字符串版本信息 (FileVersion) ===")
        print(f"  偏移地址: 0x{self.file_version_string_offset:X}")
        print(f"  当前版本: {version_string}")
        print(f"  解析: Major={self.current_version.major}, Minor={self.current_version.minor}, "
              f"Build={self.current_version.build}, Release={self.current_version.release}")
        
        return True
    
    def analyze(self) -> bool:
        """分析 .res 文件"""
        if not self.load():
            return False
        if not self.find_binary_version():
            return False
        if not self.find_string_version():
            return False
        return True
    
    def calculate_new_version(self, new_build: Optional[int] = None) -> VersionInfo:
        """计算新版本号 (修改 Build 字段)"""
        if self.current_version is None:
            raise RuntimeError("未分析版本信息")
        
        if new_build is None:
            new_build = self.current_version.build + 1
        
        self.new_version = VersionInfo(
            major=self.current_version.major,
            minor=self.current_version.minor,
            build=new_build,  # 更新 Build
            release=self.current_version.release  # 保持 Release 不变
        )
        
        return self.new_version
    
    def update_binary_version(self):
        """更新二进制版本号 (修改 FileVersionLS 和 ProductVersionLS 的高16位)"""
        if self.new_version is None:
            raise RuntimeError("未计算新版本号")
        
        new_build = self.new_version.build
        
        # FileVersionLS: 高16位是 Build，低16位是 Release
        # 我们只修改高16位 (Build)
        
        # 偏移 +2 是 Build 所在的位置 (因为是小端序，低字节在前)
        build_offset = self.file_version_ls_offset + 2
        
        old_bytes = self.data[build_offset:build_offset + 2]
        old_value = f"0x{old_bytes[1]:02X}{old_bytes[0]:02X} ({struct.unpack_from('<H', self.data, build_offset)[0]})"
        
        # 写入新的 Build 值
        struct.pack_into('<H', self.data, build_offset, new_build)
        
        new_bytes = self.data[build_offset:build_offset + 2]
        new_value = f"0x{new_bytes[1]:02X}{new_bytes[0]:02X} ({new_build})"
        
        self.modifications.append(ModificationRecord(
            file=".res",
            location=f"0x{build_offset:X}",
            type_desc="FileVersionLS.Build (二进制)",
            old_value=old_value,
            new_value=new_value
        ))
        
        # 注意: 不更新 ProductVersionLS，因为它在 Delphi 项目中通常独立设置
    
    def update_string_version(self) -> bool:
        """更新字符串版本号 (支持跨位数升级，如 9->10, 99->100)"""
        if self.current_version is None or self.new_version is None:
            raise RuntimeError("版本信息未初始化")
        
        old_build_str = str(self.current_version.build)
        new_build_str = str(self.new_version.build)
        
        len_diff = len(new_build_str) - len(old_build_str)
        
        if len_diff == 0:
            # 长度相同，直接替换
            return self._update_string_version_same_length(old_build_str, new_build_str)
        else:
            # 长度不同，需要调整结构
            return self._update_string_version_diff_length(old_build_str, new_build_str, len_diff)
    
    def _update_string_version_same_length(self, old_build_str: str, new_build_str: str) -> bool:
        """更新字符串版本号 (长度相同)"""
        # 在版本字符串中找到 Build 部分的位置
        version_start = self.file_version_string_offset
        dot_count = 0
        build_str_offset = -1
        
        i = version_start
        while i < len(self.data) - 1:
            char_code = struct.unpack_from('<H', self.data, i)[0]
            if char_code == 0:
                break
            if char_code == ord('.'):
                dot_count += 1
                if dot_count == 2:
                    build_str_offset = i + 2
                    break
            i += 2
        
        if build_str_offset == -1:
            print_warning("警告: 无法定位 Build 字符串位置")
            return False
        
        # 更新 Build 字符串
        for j, char in enumerate(new_build_str):
            struct.pack_into('<H', self.data, build_str_offset + j * 2, ord(char))
        
        self.modifications.append(ModificationRecord(
            file=".res",
            location=f"0x{build_str_offset:X}",
            type_desc="FileVersion 字符串 (Build)",
            old_value=old_build_str,
            new_value=new_build_str
        ))
        
        # 更新所有其他版本字符串
        self._update_all_version_strings(old_build_str, new_build_str)
        
        return True
    
    def _update_string_version_diff_length(self, old_build_str: str, new_build_str: str, len_diff: int) -> bool:
        """更新字符串版本号 (长度不同，需要调整结构)"""
        # 字节差异 = 字符差异 * 2 (UTF-16-LE)
        byte_diff = len_diff * 2
        
        # Windows 资源文件需要 4 字节对齐，计算对齐后的总字节差异
        # FileVersion 条目的 wLength 只增加实际的字节数
        # 但外层结构需要按 4 字节对齐
        aligned_byte_diff = ((byte_diff + 3) // 4) * 4  # 向上取整到 4 的倍数
        
        print_info(f"  版本号长度变化: {len(old_build_str)} -> {len(new_build_str)} (字节差异: {byte_diff:+d}, 对齐后: {aligned_byte_diff:+d})")
        
        # 1. 查找 FileVersion 字符串条目的位置
        file_version_key = "FileVersion".encode('utf-16-le')
        fv_key_pos = self.data.find(file_version_key)
        if fv_key_pos == -1:
            print_error("错误: 无法找到 FileVersion 字符串")
            return False
        
        # FileVersion 条目头在 key 前面 6 字节 (wLength + wValueLength + wType)
        fv_entry_offset = fv_key_pos - 6
        
        # 2. 读取当前的长度值
        fv_wLength = struct.unpack_from('<H', self.data, fv_entry_offset)[0]
        fv_wValueLength = struct.unpack_from('<H', self.data, fv_entry_offset + 2)[0]
        
        # 3. 查找版本字符串值的起始位置
        version_start = self.file_version_string_offset
        
        # 找到 Build 数字的起始位置
        dot_count = 0
        build_str_offset = -1
        i = version_start
        while i < len(self.data) - 1:
            char_code = struct.unpack_from('<H', self.data, i)[0]
            if char_code == 0:
                break
            if char_code == ord('.'):
                dot_count += 1
                if dot_count == 2:
                    build_str_offset = i + 2
                    break
            i += 2
        
        if build_str_offset == -1:
            print_error("错误: 无法定位 Build 字符串位置")
            return False
        
        # 找到 Build 数字的结束位置 (下一个点或字符串结束)
        build_end_offset = build_str_offset
        while build_end_offset < len(self.data) - 1:
            char_code = struct.unpack_from('<H', self.data, build_end_offset)[0]
            if char_code == ord('.') or char_code == 0:
                break
            build_end_offset += 2
        
        # 4. 找到 FileVersion 条目的结束位置（当前条目结束后下一个条目开始处）
        # FileVersion 条目结束于 fv_entry_offset + fv_wLength
        fv_entry_end = fv_entry_offset + fv_wLength
        
        # 5. 构建新的 Build 字符串字节
        new_build_bytes = new_build_str.encode('utf-16-le')
        
        # 6. 执行替换：替换 Build 部分
        after_build = self.data[build_end_offset:]
        self.data = self.data[:build_str_offset] + bytearray(new_build_bytes) + after_build
        
        self.modifications.append(ModificationRecord(
            file=".res",
            location=f"0x{build_str_offset:X}",
            type_desc="FileVersion 字符串 (Build)",
            old_value=old_build_str,
            new_value=new_build_str
        ))
        
        # 7. 计算并插入填充字节（保持 4 字节对齐）
        # 新的 FileVersion 条目结束位置
        new_fv_entry_end = fv_entry_offset + fv_wLength + byte_diff
        # 需要的填充字节数（使下一个条目 4 字节对齐）
        padding_needed = aligned_byte_diff - byte_diff
        
        if padding_needed > 0:
            # 在当前条目结束位置插入填充字节
            # 由于已经插入了 byte_diff 字节，FileVersion 条目现在结束于新位置
            # 找到字符串值的结束位置（null terminator 之后）
            # 新的字符串结束位置 = 原始结束位置 + byte_diff
            string_end_offset = fv_entry_end + byte_diff
            
            # 插入填充字节
            self.data = self.data[:string_end_offset] + bytearray(padding_needed) + self.data[string_end_offset:]
        
        # 8. 更新所有长度字段
        self._update_length_fields(byte_diff, aligned_byte_diff, fv_entry_offset)
        
        # 9. 更新所有其他版本字符串 (ProductVersion 等)
        self._update_all_version_strings_with_length_change(old_build_str, new_build_str)
        
        return True
    
    def _update_length_fields(self, byte_diff: int, aligned_byte_diff: int, fv_entry_offset: int):
        """更新所有相关的长度字段"""
        # 资源块数据大小字段位置 (这些是固定的)
        # 0x0020: 资源块 DataSize
        # 0x0040: 资源块 DataSize (副本)
        # 这些字段使用对齐后的字节差异
        resource_size_offsets = [0x0020, 0x0040]
        
        for offset in resource_size_offsets:
            if offset < len(self.data) - 2:
                old_val = struct.unpack_from('<H', self.data, offset)[0]
                new_val = old_val + aligned_byte_diff
                struct.pack_into('<H', self.data, offset, new_val)
                self.modifications.append(ModificationRecord(
                    file=".res",
                    location=f"0x{offset:04X}",
                    type_desc="资源块 DataSize",
                    old_value=str(old_val),
                    new_value=str(new_val)
                ))
        
        # StringFileInfo wLength (0x009C) - 使用对齐后的字节差异
        sfi_offset = 0x009C
        if sfi_offset < len(self.data) - 2:
            old_val = struct.unpack_from('<H', self.data, sfi_offset)[0]
            new_val = old_val + aligned_byte_diff
            struct.pack_into('<H', self.data, sfi_offset, new_val)
            self.modifications.append(ModificationRecord(
                file=".res",
                location=f"0x{sfi_offset:04X}",
                type_desc="StringFileInfo wLength",
                old_value=str(old_val),
                new_value=str(new_val)
            ))
        
        # StringTable wLength (0x00C0) - 使用对齐后的字节差异
        st_offset = 0x00C0
        if st_offset < len(self.data) - 2:
            old_val = struct.unpack_from('<H', self.data, st_offset)[0]
            new_val = old_val + aligned_byte_diff
            struct.pack_into('<H', self.data, st_offset, new_val)
            self.modifications.append(ModificationRecord(
                file=".res",
                location=f"0x{st_offset:04X}",
                type_desc="StringTable wLength",
                old_value=str(old_val),
                new_value=str(new_val)
            ))
        
        # FileVersion 条目: wLength 和 wValueLength (0x015C, 0x015E)
        # FileVersion wLength 使用实际字节差异 (不包括外部填充)
        fv_wLength_offset = 0x015C
        fv_wValueLength_offset = 0x015E
        
        if fv_wLength_offset < len(self.data) - 2:
            old_val = struct.unpack_from('<H', self.data, fv_wLength_offset)[0]
            new_val = old_val + byte_diff
            struct.pack_into('<H', self.data, fv_wLength_offset, new_val)
            self.modifications.append(ModificationRecord(
                file=".res",
                location=f"0x{fv_wLength_offset:04X}",
                type_desc="FileVersion wLength",
                old_value=str(old_val),
                new_value=str(new_val)
            ))
        
        if fv_wValueLength_offset < len(self.data) - 2:
            old_val = struct.unpack_from('<H', self.data, fv_wValueLength_offset)[0]
            # wValueLength 是字符数，不是字节数
            char_diff = byte_diff // 2
            new_val = old_val + char_diff
            struct.pack_into('<H', self.data, fv_wValueLength_offset, new_val)
            self.modifications.append(ModificationRecord(
                file=".res",
                location=f"0x{fv_wValueLength_offset:04X}",
                type_desc="FileVersion wValueLength",
                old_value=str(old_val),
                new_value=str(new_val)
            ))
    
    def _update_all_version_strings(self, old_build: str, new_build: str):
        """更新文件中所有的版本字符串 (长度相同时)"""
        # 构建搜索模式: ".X." (Unicode)，X 是 build 号
        old_pattern = f".{old_build}.".encode('utf-16-le')
        new_pattern = f".{new_build}.".encode('utf-16-le')
        
        pos = 0
        count = 0
        while True:
            pos = self.data.find(old_pattern, pos)
            if pos == -1:
                break
            
            # 替换
            for i, byte in enumerate(new_pattern):
                self.data[pos + i] = byte
            
            count += 1
            pos += len(old_pattern)
        
        if count > 1:
            print_info(f"  (共更新 {count} 处版本字符串)")
    
    def _update_all_version_strings_with_length_change(self, old_build: str, new_build: str):
        """更新文件中所有的版本字符串 (长度不同时，逐个查找替换)"""
        # 构建完整版本号的搜索模式
        old_version = f"{self.current_version.major}.{self.current_version.minor}.{old_build}.{self.current_version.release}"
        new_version = f"{self.new_version.major}.{self.new_version.minor}.{new_build}.{self.new_version.release}"
        
        old_pattern = old_version.encode('utf-16-le')
        new_pattern = new_version.encode('utf-16-le')
        
        byte_diff = len(new_pattern) - len(old_pattern)
        
        # 查找所有匹配位置 (从后往前替换，避免偏移问题)
        positions = []
        pos = 0
        while True:
            pos = self.data.find(old_pattern, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += len(old_pattern)
        
        # 从后往前替换
        for pos in reversed(positions[1:]):  # 跳过第一个 FileVersion (已经处理过)
            self.data = self.data[:pos] + bytearray(new_pattern) + self.data[pos + len(old_pattern):]
        
        if len(positions) > 1:
            print_info(f"  (共更新 {len(positions)} 处版本字符串)")
    
    def save(self, backup: bool = True) -> bool:
        """保存修改后的文件"""
        if backup:
            backup_file = f"{self.res_file}.bak"
            shutil.copy2(self.res_file, backup_file)
            print_info(f"已备份原文件到: {backup_file}")
        
        with open(self.res_file, 'wb') as f:
            f.write(self.data)
        
        return True
    
    def print_summary(self):
        """打印修改摘要"""
        print()
        print_info("=== 修改摘要 ===")
        print(f"{"文件":<8} {"位置":<12} {"类型":<30} {"原值":<15} {"新值":<15}")
        print("-" * 85)
        for mod in self.modifications:
            print(f"{mod.file:<8} {mod.location:<12} {mod.type_desc:<30} {mod.old_value:<15} {mod.new_value:<15}")
    
    def bump(self, new_build: Optional[int] = None, dry_run: bool = False) -> bool:
        """
        执行版本号升级
        
        Args:
            new_build: 指定新的 Build 号，None 表示自动 +1
            dry_run: 预览模式，不实际保存文件
        
        Returns:
            是否成功
        """
        print()
        print_colored("=" * 55, Colors.HEADER)
        print_colored("   Delphi .res 版本号升级工具 v1.0", Colors.HEADER)
        print_colored("=" * 55, Colors.HEADER)
        print()
        
        # 1. 分析文件
        if not self.analyze():
            return False
        
        # 2. 计算新版本号
        self.calculate_new_version(new_build)
        
        print()
        print_success("=== 版本号变更 ===")
        print(f"  当前版本: {Colors.YELLOW}{self.current_version}{Colors.ENDC}")
        print(f"  新版本:   {Colors.GREEN}{self.new_version}{Colors.ENDC}")
        
        if dry_run:
            print()
            print_warning("[预览模式] 以下修改将被执行但不会保存:")
        
        # 3. 执行修改
        self.update_binary_version()
        self.update_string_version()
        
        # 4. 显示摘要
        self.print_summary()
        
        # 5. 保存文件
        if not dry_run:
            if self.save():
                print()
                print_success("=" * 55)
                print_success(f"  ✓ 版本号已从 {self.current_version} 升级到 {self.new_version}")
                print_success("=" * 55)
        else:
            print()
            print_warning("[预览模式] 未保存任何更改")
        
        print()
        return True


class ProjectVersionBumper:
    """Delphi 项目版本号升级器 (同时处理 .res 和 .dproj 文件)"""
    
    def __init__(self, project_dir: str):
        self.project_dir = os.path.abspath(project_dir)
        self.res_file: Optional[str] = None
        self.dproj_file: Optional[str] = None
        self.res_bumper: Optional[ResVersionBumper] = None
        self.dproj_bumper: Optional[DprojVersionBumper] = None
        self.current_version: Optional[VersionInfo] = None
        self.new_version: Optional[VersionInfo] = None
    
    def find_files(self) -> bool:
        """查找项目中的 .res 和 .dproj 文件"""
        if os.path.isfile(self.project_dir):
            # 如果传入的是文件，获取其目录
            self.project_dir = os.path.dirname(self.project_dir)
        
        if not os.path.isdir(self.project_dir):
            print_error(f"错误: 目录不存在 - {self.project_dir}")
            return False
        
        # 查找 .res 和 .dproj 文件
        for file in os.listdir(self.project_dir):
            file_path = os.path.join(self.project_dir, file)
            if file.lower().endswith('.res') and self.res_file is None:
                self.res_file = file_path
            elif file.lower().endswith('.dproj') and self.dproj_file is None:
                self.dproj_file = file_path
        
        if not self.res_file:
            print_error(f"错误: 在 {self.project_dir} 中找不到 .res 文件")
            return False
        
        if not self.dproj_file:
            print_error(f"错误: 在 {self.project_dir} 中找不到 .dproj 文件")
            return False
        
        print_info(f"项目目录: {self.project_dir}")
        print_info(f"资源文件: {os.path.basename(self.res_file)}")
        print_info(f"项目文件: {os.path.basename(self.dproj_file)}")
        
        return True
    
    def bump(self, new_build: Optional[int] = None, dry_run: bool = False) -> bool:
        """
        执行版本号升级
        
        Args:
            new_build: 指定新的 Build 号，None 表示自动 +1
            dry_run: 预览模式，不实际保存文件
        
        Returns:
            是否成功
        """
        print()
        print_colored("=" * 60, Colors.HEADER)
        print_colored("     Delphi 版本号升级工具 v2.0", Colors.HEADER)
        print_colored("     同时更新 .res 和 .dproj 文件", Colors.HEADER)
        print_colored("=" * 60, Colors.HEADER)
        print()
        
        # 1. 查找文件
        if not self.find_files():
            return False
        
        # 2. 初始化处理器
        self.res_bumper = ResVersionBumper(self.res_file)
        self.dproj_bumper = DprojVersionBumper(self.dproj_file)
        
        # 3. 分析 .res 文件
        print()
        print_colored(">>> 分析 .res 文件", Colors.BLUE)
        if not self.res_bumper.analyze():
            return False
        
        # 4. 分析 .dproj 文件
        print()
        print_colored(">>> 分析 .dproj 文件", Colors.BLUE)
        if not self.dproj_bumper.analyze():
            return False
        
        # 5. 验证版本号一致性
        res_ver = self.res_bumper.current_version
        dproj_ver = self.dproj_bumper.current_version
        
        if res_ver.build != dproj_ver.build:
            print_warning(f"警告: .res ({res_ver}) 和 .dproj ({dproj_ver}) 版本号不一致!")
        
        self.current_version = res_ver
        
        # 6. 计算新版本号
        if new_build is None:
            new_build = self.current_version.build + 1
        
        self.new_version = VersionInfo(
            major=self.current_version.major,
            minor=self.current_version.minor,
            build=new_build,
            release=self.current_version.release
        )
        
        self.res_bumper.new_version = self.new_version
        self.dproj_bumper.new_version = self.new_version
        
        print()
        print_success("=" * 60)
        print_success(f"  版本号变更: {Colors.YELLOW}{self.current_version}{Colors.ENDC} -> {Colors.GREEN}{self.new_version}{Colors.ENDC}")
        print_success("=" * 60)
        
        if dry_run:
            print()
            print_warning("[预览模式] 以下修改将被执行但不会保存:")
        
        # 7. 执行修改
        print()
        print_colored(">>> 更新 .res 文件", Colors.BLUE)
        self.res_bumper.update_binary_version()
        self.res_bumper.update_string_version()
        
        print()
        print_colored(">>> 更新 .dproj 文件", Colors.BLUE)
        self.dproj_bumper.update(new_build)
        
        # 8. 汇总所有修改
        all_modifications = self.res_bumper.modifications + self.dproj_bumper.modifications
        
        print()
        print_info("=== 修改摘要 ===")
        print(f"{'文件':<8} {'位置':<16} {'类型':<28} {'原值':<18} {'新值':<18}")
        print("-" * 90)
        for mod in all_modifications:
            print(f"{mod.file:<8} {mod.location:<16} {mod.type_desc:<28} {mod.old_value:<18} {mod.new_value:<18}")
        
        # 9. 保存文件
        if not dry_run:
            print()
            self.res_bumper.save()
            self.dproj_bumper.save()
            
            print()
            print_success("=" * 60)
            print_success(f"  ✓ 版本号已从 {self.current_version} 升级到 {self.new_version}")
            print_success(f"  ✓ 已更新文件:")
            print_success(f"      - {os.path.basename(self.res_file)}")
            print_success(f"      - {os.path.basename(self.dproj_file)}")
            print_success("=" * 60)
        else:
            print()
            print_warning("[预览模式] 未保存任何更改")
        
        print()
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Delphi 版本号自动升级工具 (同时更新 .res 和 .dproj 文件)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s ./10_2503_6             # 自动将版本号 Build +1 (如 10.2503.6.0 -> 10.2503.7.0)
  %(prog)s ./10_2503_6 --build 8   # 将 Build 设置为 8
  %(prog)s ./10_2503_6 --dry-run   # 预览模式，不实际修改
  %(prog)s TubePro.res             # 也可以直接指定 .res 文件
        '''
    )
    
    parser.add_argument('project_path', help='项目目录或 .res 文件路径')
    parser.add_argument('--build', '-b', type=int, default=None,
                        help='指定新的 Build 号 (默认: 自动 +1)')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='预览模式，不实际修改文件')
    
    args = parser.parse_args()
    
    # 启用 Windows 终端的 ANSI 颜色支持
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass
    
    bumper = ProjectVersionBumper(args.project_path)
    success = bumper.bump(new_build=args.build, dry_run=args.dry_run)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
