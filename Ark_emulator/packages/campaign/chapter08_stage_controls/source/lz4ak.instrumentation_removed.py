from typing import Union
import lz4
import lz4.block
ByteString = Union[bytes, bytearray, memoryview]

def _read_extra_length(data: ByteString, cur_pos: int, max_pos: int) -> tuple[int, int]:
    l = 0
    while cur_pos < max_pos:
        b = data[cur_pos]
        l += b
        cur_pos += 1
        if b != 255:
            break
    return (l, cur_pos)

def decompress_lz4ak(compressed_data: ByteString, uncompressed_size: int) -> bytes:
    """Decompresses the given data block using LZ4AK algorithm.

    *Special thanks to Kengxxiao (https://github.com/Kengxxiao).*

    *Algorithm adapted from MooncellWiki:UnityPy (https://github.com/MooncellWiki/UnityPy)*

    :param compressed_data: The raw compressed data bytes;
    :param uncompressed_size: The size of the uncompressed data;
    :returns: The decompressed data bytes;
    :rtype: bytes;
    """
    ip = 0
    op = 0
    fixed_compressed_data = bytearray(compressed_data)
    compressed_size = len(compressed_data)
    while ip < compressed_size:
        literal_length = fixed_compressed_data[ip] & 15
        match_length = fixed_compressed_data[ip] >> 4 & 15
        fixed_compressed_data[ip] = literal_length << 4 | match_length
        ip += 1
        if literal_length == 15:
            l, ip = _read_extra_length(fixed_compressed_data, ip, compressed_size)
            literal_length += l
        ip += literal_length
        op += literal_length
        if op >= uncompressed_size:
            break
        offset = fixed_compressed_data[ip] << 8 | fixed_compressed_data[ip + 1]
        fixed_compressed_data[ip] = offset & 255
        fixed_compressed_data[ip + 1] = offset >> 8 & 255
        ip += 2
        if match_length == 15:
            l, ip = _read_extra_length(fixed_compressed_data, ip, compressed_size)
            match_length += l
        match_length += 4
        op += match_length
    return lz4.block.decompress(fixed_compressed_data, uncompressed_size)
