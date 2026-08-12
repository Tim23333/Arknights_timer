// memsrv — 设备侧常驻内存读取/扫描服务 (明日方舟内存工具)
//
// 由 nc -L 以 socket 作为 stdin/stdout 启动,  argv[1] 为目标 PID。
// 打开 /proc/<pid>/mem 一次, 之后每次读取仅一个 pread 系统调用。
//
// 协议 (全部小端):
//   启动: 写出 8 字节横幅 "AKMSRV4\n"
//   合并读取: u64 == PACKED_READ_MAGIC, u64 N, 随后 N 组 { u64 addr, u64 size }
//         响应: { u64 N, i64 lengths[N], u8 data[sum(max(length, 0))] }
//         整批响应只做一次 write，避免每个小读取分别写长度和数据。
//   读取事务: u64 == TXN_READ_MAGIC, u64 N, 随后 N 组 TxnReq
//         TxnReq = { u32 kind, u32 ref, i64 value, i64 offset, u64 size }
//         kind=0: addr=(u64)value；kind=1: addr=u64(result[ref]+offset)+value。
//         各操作在设备侧按顺序执行，响应格式同合并读取。
//   上传常驻计划: u64 == PLAN_UPLOAD_MAGIC, { u64 N, u64 guard_addr,
//         u32 guard_size, u32 max_attempts }, 随后 N 组 TxnReq；响应 u64 N。
//   执行常驻计划: u64 == PLAN_EXEC_MAGIC；设备内部以 guard 起止值检查完整帧，
//         跨帧时原地重读，响应 { u64 attempts, u64 guard_start, u64 guard_end }
//         后紧跟合并读取响应。稳定帧不再上传数百项事务描述。
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
#define PACKED_READ_MAGIC 0xFFFFFFFFFFFFFFFEULL
#define TXN_READ_MAGIC 0xFFFFFFFFFFFFFFFDULL
#define PLAN_UPLOAD_MAGIC 0xFFFFFFFFFFFFFFFCULL
#define PLAN_EXEC_MAGIC 0xFFFFFFFFFFFFFFFBULL
#define MAX_BATCH_BYTES (64 * 1024 * 1024)

typedef struct {
    uint64_t addr;
    uint64_t size;
} ReadReq;

typedef struct {
    uint32_t kind;
    uint32_t ref;
    int64_t value;
    int64_t offset;
    uint64_t size;
} TxnReq;

static TxnReq *saved_plan = NULL;
static uint64_t saved_plan_count = 0;
static uint64_t saved_guard_addr = 0;
static uint32_t saved_guard_size = 0;
static uint32_t saved_max_attempts = 1;

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

/*
 * 执行合并读取并一次写出完整响应。result_offsets/result_lengths 同时保留
 * 每个结果在响应缓冲区中的位置，供后续事务操作引用前序读取出的指针。
 */
static int build_packed_response(int fd, const ReadReq *reqs, uint64_t n,
                                 int allow_refs, const TxnReq *txn,
                                 uint8_t **response_out, size_t *response_size_out) {
    if (n == 0 || n > MAX_REQ) return -1;

    uint64_t declared = 0;
    for (uint64_t i = 0; i < n; i++) {
        uint64_t size = allow_refs ? txn[i].size : reqs[i].size;
        if (size == 0 || size > MAX_SIZE) continue;
        if (declared > MAX_BATCH_BYTES - size) return -1;
        declared += size;
    }
    size_t header_size = sizeof(uint64_t) + (size_t)n * sizeof(int64_t);
    if (header_size > SIZE_MAX - (size_t)declared) return -1;
    uint8_t *response = (uint8_t *)malloc(header_size + (size_t)declared);
    uint64_t *result_offsets = (uint64_t *)calloc((size_t)n, sizeof(uint64_t));
    if (!response || !result_offsets) {
        free(response);
        free(result_offsets);
        return -1;
    }
    int64_t *lengths = (int64_t *)(response + sizeof(uint64_t));
    memcpy(response, &n, sizeof(n));
    uint64_t payload_used = 0;

    for (uint64_t i = 0; i < n; i++) {
        uint64_t addr = 0;
        uint64_t size = allow_refs ? txn[i].size : reqs[i].size;
        int invalid = (size == 0 || size > MAX_SIZE);
        if (!invalid && !allow_refs) {
            addr = reqs[i].addr;
        } else if (!invalid && txn[i].kind == 0) {
            addr = (uint64_t)txn[i].value;
        } else if (!invalid && txn[i].kind == 1) {
            uint32_t ref = txn[i].ref;
            int64_t off = txn[i].offset;
            if (ref >= i || lengths[ref] <= 0 || off < 0
                    || (uint64_t)off + sizeof(uint64_t) > (uint64_t)lengths[ref]) {
                invalid = 1;
            } else {
                uint64_t base = 0;
                memcpy(&base, response + result_offsets[ref] + (size_t)off,
                       sizeof(base));
                addr = base + (uint64_t)txn[i].value;
            }
        } else if (!invalid) {
            invalid = 1;
        }

        result_offsets[i] = (uint64_t)header_size + payload_used;
        if (invalid) {
            lengths[i] = -EINVAL;
            continue;
        }
        ssize_t r;
        do {
            r = pread(fd, response + header_size + payload_used,
                      (size_t)size, (off_t)addr);
        } while (r < 0 && errno == EINTR);
        lengths[i] = r < 0 ? -(int64_t)errno : (int64_t)r;
        if (r > 0) payload_used += (uint64_t)r;
    }

    free(result_offsets);
    *response_out = response;
    *response_size_out = header_size + (size_t)payload_used;
    return 0;
}

static int do_packed_reads(int fd, const ReadReq *reqs, uint64_t n,
                           int allow_refs, const TxnReq *txn) {
    uint8_t *response = NULL;
    size_t response_size = 0;
    if (build_packed_response(fd, reqs, n, allow_refs, txn,
                              &response, &response_size) < 0)
        return -1;
    int rc = write_exact(1, response, response_size);
    free(response);
    return rc;
}

static uint64_t read_guard_value(int fd, uint64_t addr, uint32_t size) {
    uint64_t value = UINT64_MAX;
    if (!addr || (size != 4 && size != 8)) return value;
    value = 0;
    ssize_t r;
    do {
        r = pread(fd, &value, size, (off_t)addr);
    } while (r < 0 && errno == EINTR);
    return r == (ssize_t)size ? value : UINT64_MAX;
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

    if (write_exact(1, "AKMSRV4\n", 8) < 0) return 4;

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

        if (n == PACKED_READ_MAGIC) {
            uint64_t count = 0;
            if (read_exact(0, &count, sizeof(count)) < 0) return 0;
            if (count == 0 || count > MAX_REQ) return 11;
            ReadReq *reqs = (ReadReq *)malloc((size_t)count * sizeof(ReadReq));
            if (!reqs) return 12;
            if (read_exact(0, reqs, (size_t)count * sizeof(ReadReq)) < 0) {
                free(reqs);
                return 0;
            }
            int rc = do_packed_reads(fd, reqs, count, 0, NULL);
            free(reqs);
            if (rc < 0) return 13;
            continue;
        }

        if (n == TXN_READ_MAGIC) {
            uint64_t count = 0;
            if (read_exact(0, &count, sizeof(count)) < 0) return 0;
            if (count == 0 || count > MAX_REQ) return 14;
            TxnReq *txn = (TxnReq *)malloc((size_t)count * sizeof(TxnReq));
            if (!txn) return 15;
            if (read_exact(0, txn, (size_t)count * sizeof(TxnReq)) < 0) {
                free(txn);
                return 0;
            }
            int rc = do_packed_reads(fd, NULL, count, 1, txn);
            free(txn);
            if (rc < 0) return 16;
            continue;
        }

        if (n == PLAN_UPLOAD_MAGIC) {
            uint64_t header[2];
            uint32_t options[2];
            if (read_exact(0, header, sizeof(header)) < 0) return 0;
            if (read_exact(0, options, sizeof(options)) < 0) return 0;
            uint64_t count = header[0];
            if (count == 0 || count > MAX_REQ) return 18;
            if (options[0] != 0 && options[0] != 4 && options[0] != 8) return 19;
            TxnReq *plan = malloc((size_t)count * sizeof(TxnReq));
            if (!plan) return 20;
            if (read_exact(0, plan, (size_t)count * sizeof(TxnReq)) < 0) {
                free(plan);
                return 0;
            }
            free(saved_plan);
            saved_plan = plan;
            saved_plan_count = count;
            saved_guard_addr = header[1];
            saved_guard_size = options[0];
            saved_max_attempts = options[1];
            if (saved_max_attempts < 1) saved_max_attempts = 1;
            if (saved_max_attempts > 8) saved_max_attempts = 8;
            if (write_exact(1, &saved_plan_count, sizeof(saved_plan_count)) < 0)
                return 21;
            continue;
        }

        if (n == PLAN_EXEC_MAGIC) {
            if (!saved_plan || saved_plan_count == 0) return 22;
            uint8_t *response = NULL;
            size_t response_size = 0;
            uint64_t attempts = 0;
            uint64_t guard_start = UINT64_MAX, guard_end = UINT64_MAX;
            for (uint32_t attempt = 0; attempt < saved_max_attempts; attempt++) {
                free(response);
                response = NULL;
                response_size = 0;
                guard_start = read_guard_value(
                    fd, saved_guard_addr, saved_guard_size);
                if (build_packed_response(fd, NULL, saved_plan_count, 1,
                                          saved_plan, &response,
                                          &response_size) < 0) {
                    free(response);
                    return 23;
                }
                guard_end = read_guard_value(fd, saved_guard_addr, saved_guard_size);
                attempts = (uint64_t)attempt + 1;
                if (!saved_guard_addr || (guard_start != UINT64_MAX
                        && guard_start == guard_end)) break;
            }
            uint64_t meta[3] = { attempts, guard_start, guard_end };
            if (write_exact(1, meta, sizeof(meta)) < 0
                    || write_exact(1, response, response_size) < 0) {
                free(response);
                return 24;
            }
            free(response);
            continue;
        }

        // 不兼容旧协议的普通读取命令，也不把未知命令解释为请求数量。
        return 25;
    }
}
