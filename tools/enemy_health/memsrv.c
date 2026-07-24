// memsrv — 设备侧常驻内存读取/扫描服务 (明日方舟内存工具)
//
// 由 nc -L 以 socket 作为 stdin/stdout 启动,  argv[1] 为目标 PID。
// 打开 /proc/<pid>/mem 一次, 之后每次读取仅一个 pread 系统调用。
//
// 协议 (全部小端):
//   启动: 写出 8 字节横幅 "AKMSRV2\n" (v2: 支持扫描命令)
//   读取: u64 N (1..4096), 随后 N 组 { u64 addr, u64 size }
//         响应: 每组 { i64 n, u8 data[n] };  n<0 表示 -errno, n<size 为短读
//   扫描: u64 == SCAN_MAGIC, 随后 { u64 addr, u64 size, u32 k },
//         随后 k 组 { u32 len, u8 needle[len] } (len ≤ 64)
//         响应: k 组 { i64 count, count × u64 hit_addr }
//         设备侧分块 pread + 模式匹配, 命中为绝对地址, 单针上限 MAX_HITS
//         全部针为 8 字节时走 u64 对齐哈希快路径 (指针扫描)
//   N==0 或 stdin EOF -> 退出
//
// 构建: python -m ziglang cc -target aarch64-linux-musl -static -O2 -o memsrv memsrv.c
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_REQ 4096                // 单批最多读取请求数
#define MAX_SIZE (4 * 1024 * 1024)  // 单请求最大字节 (也是扫描分块)
#define MAX_NEEDLES 256             // 单次扫描最多模式串
#define MAX_NEEDLE_LEN 64           // 单个模式串最大字节
#define MAX_HITS 65536              // 单针最多命中数
#define OVERLAP (MAX_NEEDLE_LEN)    // 扫描分块重叠, 覆盖跨界命中
#define SCAN_MAGIC 0xFFFFFFFFFFFFFFFFULL

static int read_exact(int fd, void *buf, size_t n) {
    char *p = (char *)buf;
    while (n > 0) {
        ssize_t r = read(fd, p, n);
        if (r == 0) return -1;            // EOF
        if (r < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        p += r; n -= (size_t)r;
    }
    return 0;
}

static int write_exact(int fd, const void *buf, size_t n) {
    const char *p = (const char *)buf;
    while (n > 0) {
        ssize_t r = write(fd, p, n);
        if (r < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        p += r; n -= (size_t)r;
    }
    return 0;
}

// ---------------- 扫描 ----------------

static uint8_t scan_buf[MAX_SIZE];
static uint8_t needles[MAX_NEEDLES][MAX_NEEDLE_LEN];
static uint32_t needle_lens[MAX_NEEDLES];

// u64 快路径用的极简开地址哈希 (指针扫描: 全部 8 字节针)
#define HASH_CAP 1024   // >= 2*MAX_NEEDLES 的 2 的幂
static uint64_t htab[HASH_CAP];
static uint8_t htab_used[HASH_CAP];
static int htab_idx[MAX_NEEDLES];       // needle -> 哈希槽 (命中时反查 needle 序号)

static void htab_build(const uint64_t *vals, int k) {
    memset(htab_used, 0, sizeof(htab_used));
    for (int i = 0; i < k; i++) {
        uint64_t h = (vals[i] >> 3) * 0x9E3779B97F4A7C15ULL;
        uint32_t slot = (uint32_t)(h >> 32) & (HASH_CAP - 1);
        while (htab_used[slot]) slot = (slot + 1) & (HASH_CAP - 1);
        htab_used[slot] = 1;
        htab[slot] = vals[i];
        htab_idx[i] = (int)slot;
    }
}

static int htab_lookup(uint64_t v, int *slot_out) {
    uint64_t h = (v >> 3) * 0x9E3779B97F4A7C15ULL;
    uint32_t slot = (uint32_t)(h >> 32) & (HASH_CAP - 1);
    while (htab_used[slot]) {
        if (htab[slot] == v) { *slot_out = (int)slot; return 1; }
        slot = (slot + 1) & (HASH_CAP - 1);
    }
    return 0;
}

// 执行一次扫描: 窗口滑动 pread, 相邻窗口重叠 OVERLAP 字节覆盖跨界命中;
// 每窗口只接受落在其有效载荷区 [0, payload_limit) 内的命中 (无重复无遗漏)
static void do_scan(int fd, uint64_t addr, uint64_t size, uint32_t k,
                    int64_t *counts, uint64_t **hit_lists) {
    int u64_mode = 1;
    for (uint32_t i = 0; i < k; i++)
        if (needle_lens[i] != 8) { u64_mode = 0; break; }

    uint64_t needle_u64[MAX_NEEDLES];
    int slot_to_needle[HASH_CAP];
    if (u64_mode) {
        for (uint32_t i = 0; i < k; i++)
            memcpy(&needle_u64[i], needles[i], 8);
        htab_build(needle_u64, (int)k);
        memset(slot_to_needle, -1, sizeof(slot_to_needle));
        for (uint32_t i = 0; i < k; i++) slot_to_needle[htab_idx[i]] = (int)i;
    }

    uint64_t pos = addr, end = addr + size;
    while (pos < end) {
        uint64_t want = end - pos;
        if (want > MAX_SIZE) want = MAX_SIZE;
        ssize_t r;
        do {
            r = pread(fd, scan_buf, want, (off_t)pos);
        } while (r < 0 && errno == EINTR);
        if (r <= 0) break;                 // 洞/EIO: 终止, 返回已收集命中
        size_t got = (size_t)r;
        int final = (pos + got >= end) || (got < (size_t)want);
        size_t payload = final ? got : (got > OVERLAP ? got - OVERLAP : 0);

        if (u64_mode) {
            size_t start = (size_t)((8 - (pos & 7)) & 7);
            for (size_t off = start; off < payload && off + 8 <= got; off += 8) {
                uint64_t v;
                memcpy(&v, scan_buf + off, 8);
                int slot;
                if (htab_lookup(v, &slot)) {
                    int ni = slot_to_needle[slot];
                    if (counts[ni] < MAX_HITS)
                        hit_lists[ni][counts[ni]] = pos + off;
                    counts[ni]++;
                }
            }
        } else {
            for (uint32_t i = 0; i < k; i++) {
                uint32_t nl = needle_lens[i];
                for (size_t off = 0; off < payload;) {
                    const uint8_t *p = memchr(scan_buf + off, needles[i][0], payload - off);
                    if (!p) break;
                    size_t o = (size_t)(p - scan_buf);
                    if (o >= payload) break;
                    // 非末块: 针体必然在缓冲内 (o < payload, nl <= OVERLAP);
                    // 末块: payload==got, 需显式保证针体不越界
                    if (o + nl <= got &&
                        (nl == 1 || memcmp(p + 1, needles[i] + 1, nl - 1) == 0)) {
                        if (counts[i] < MAX_HITS)
                            hit_lists[i][counts[i]] = pos + o;
                        counts[i]++;
                    }
                    off = o + 1;
                }
            }
        }
        pos += payload > 0 ? payload : (uint64_t)got;
        if (final) break;
    }
}

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);

    if (argc < 2) return 2;
    char path[64];
    snprintf(path, sizeof(path), "/proc/%s/mem", argv[1]);
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 3;

    if (write_exact(1, "AKMSRV2\n", 8) < 0) return 4;

    static uint8_t buf[MAX_SIZE];
    for (;;) {
        uint64_t n = 0;
        if (read_exact(0, &n, 8) < 0) return 0;   // EOF: 客户端断开
        if (n == 0) return 0;

        if (n == SCAN_MAGIC) {
            // ---- 扫描命令 ----
            uint64_t hdr[2];
            uint32_t k = 0;
            if (read_exact(0, hdr, 16) < 0) return 0;
            if (read_exact(0, &k, 4) < 0) return 0;
            if (k == 0 || k > MAX_NEEDLES) return 7;
            int64_t counts[MAX_NEEDLES] = {0};
            uint64_t *hit_lists[MAX_NEEDLES];
            for (uint32_t i = 0; i < k; i++) {
                uint32_t nl = 0;
                if (read_exact(0, &nl, 4) < 0) return 0;
                if (nl == 0 || nl > MAX_NEEDLE_LEN) return 8;
                if (read_exact(0, needles[i], nl) < 0) return 0;
                needle_lens[i] = nl;
                hit_lists[i] = malloc(MAX_HITS * sizeof(uint64_t));
                if (!hit_lists[i]) return 9;
            }
            do_scan(fd, hdr[0], hdr[1], k, counts, hit_lists);
            for (uint32_t i = 0; i < k; i++) {
                int64_t c = counts[i] > MAX_HITS ? MAX_HITS : counts[i];
                if (write_exact(1, &c, 8) < 0) return 10;
                if (c > 0 && write_exact(1, hit_lists[i], (size_t)c * 8) < 0) return 10;
                free(hit_lists[i]);
            }
            continue;
        }

        // ---- 读取命令 ----
        if (n > MAX_REQ) return 5;
        for (uint64_t i = 0; i < n; i++) {
            uint64_t req[2];
            if (read_exact(0, req, 16) < 0) return 0;
            uint64_t addr = req[0], size = req[1];
            int64_t got;
            if (size == 0 || size > MAX_SIZE) {
                got = -EINVAL;
            } else {
                ssize_t r;
                do {
                    r = pread(fd, buf, size, (off_t)addr);
                } while (r < 0 && errno == EINTR);
                got = r < 0 ? -(int64_t)errno : (int64_t)r;
            }
            if (write_exact(1, &got, 8) < 0) return 6;
            if (got > 0 && write_exact(1, buf, (size_t)got) < 0) return 6;
        }
    }
}
