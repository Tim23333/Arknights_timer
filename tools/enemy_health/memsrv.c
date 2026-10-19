// memsrv — 设备侧常驻内存读取/扫描服务 (明日方舟内存工具)
//
// 由 nc -L 以 socket 作为 stdin/stdout 启动,  argv[1] 为目标 PID。
// 打开 /proc/<pid>/mem 一次, 之后每次读取仅一个 pread 系统调用。
//
// 协议 (全部小端):
//   启动: 写出 8 字节横幅 "AKMSRV5\n"
//   合并读取: u64 == PACKED_READ_MAGIC, u64 N, 随后 N 组 { u64 addr, u64 size }
//         响应: { u64 N, i64 lengths[N], u8 data[sum(max(length, 0))] }
//         整批响应只做一次 write，避免每个小读取分别写长度和数据。
//   读取事务: u64 == TXN_READ_MAGIC, u64 N, 随后 N 组 TxnReq
//         TxnReq = { u32 kind, u32 ref, i64 value, i64 offset, u64 size }
//         kind=0: addr=(u64)value；kind=1: addr=u64(result[ref]+offset)+value；
//         kind=2: offset 的低/高 32 位分别是前序结果内的数组指针/
//         int32 索引偏移，设 array=ptr(result[ref]+array_off)，读取
//         ptr(array.items[index])+value。设备侧校验 max_length 和下标边界。
//         kind=3: 同样动态定位 array.items[index]，但返回其 u64 指针，
//         便于事务末尾再读一次并校验路径对象身份。
//         kind=4: offset 低/高32位为数组指针/当前数量偏移，value=0x20；
//         size 为字节上限，只返回当前 count*8 字节。容量/短读错误拒绝。
//         kind 的 0x100 位仅用于常驻数据复用：同次尝试内地址及长度完全
//         相同的成功块可复用；kind=2/3、帧守卫及普通事务不启用此优化。
//         各操作在设备侧按顺序执行，响应格式同合并读取。
//   一次性守卫事务: u64 == GUARDED_TXN_MAGIC, { u64 N,
//         u64 guard_addr, u32 guard_size, u32 max_attempts }, 随后 N 组 TxnReq。
//         设备内以 guard 起止值相等为条件重试，响应为
//         { u64 attempts, u64 guard_start, u64 guard_end } + 合并读取响应。
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

#define MAX_REQ 8192                // 单批最多读取请求数（覆盖 300 敌人双链快照）
#define MAX_SIZE (4 * 1024 * 1024)  // 单请求最大字节 (也是扫描分块)
#define MAX_NEEDLES 256             // 单次扫描最多模式串
#define MAX_NEEDLE_LEN 64           // 单个模式串最大字节
#define MAX_HITS 65536              // 单针最多命中数
#define MAX_GUARD_ATTEMPTS 8
#define OVERLAP (MAX_NEEDLE_LEN)    // 扫描分块重叠, 覆盖跨界命中
#define SCAN_MAGIC 0xFFFFFFFFFFFFFFFFULL
#define PACKED_READ_MAGIC 0xFFFFFFFFFFFFFFFEULL
#define TXN_READ_MAGIC 0xFFFFFFFFFFFFFFFDULL
#define PLAN_UPLOAD_MAGIC 0xFFFFFFFFFFFFFFFCULL
#define PLAN_EXEC_MAGIC 0xFFFFFFFFFFFFFFFBULL
#define GUARDED_TXN_MAGIC 0xFFFFFFFFFFFFFFFAULL
#define COORDINATED_EXEC_MAGIC 0xFFFFFFFFFFFFFFF9ULL
#define MAX_BATCH_BYTES (64 * 1024 * 1024)
#define MAX_ARRAY_LENGTH (16 * 1024 * 1024ULL)

#define TXN_DIRECT 0U
#define TXN_DEREF 1U
#define TXN_ARRAY_DEREF 2U
#define TXN_ARRAY_PTR 3U
/* Current header count, not last capture's array length. size is a bound. */
#define TXN_LIST_ITEMS 4U
#define TXN_REUSE_DATA 256U
#define IL2CPP_ARRAY_MAX_LENGTH 0x18ULL
#define IL2CPP_ARRAY_ITEMS 0x20ULL

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

static int checked_add_signed(uint64_t base, int64_t delta, uint64_t *out) {
    if (delta >= 0) {
        uint64_t amount = (uint64_t)delta;
        if (base > UINT64_MAX - amount) return -1;
        *out = base + amount;
        return 0;
    }
    /* -(INT64_MIN) 在 int64_t 中溢出，用 -(x+1)+1 计算绝对值。 */
    uint64_t amount = (uint64_t)(-(delta + 1)) + 1ULL;
    if (base < amount) return -1;
    *out = base - amount;
    return 0;
}

static int read_u64_at(int fd, uint64_t addr, uint64_t *out) {
    ssize_t r;
    do {
        r = pread(fd, out, sizeof(*out), (off_t)addr);
    } while (r < 0 && errno == EINTR);
    return r == (ssize_t)sizeof(*out) ? 0 : -1;
}

static int read_u32_at(int fd, uint64_t addr, uint32_t *out) {
    ssize_t r;
    do {
        r = pread(fd, out, sizeof(*out), (off_t)addr);
    } while (r < 0 && errno == EINTR);
    return r == (ssize_t)sizeof(*out) ? 0 : -1;
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
    int has_reuse = 0;
    for (uint64_t i = 0; i < n; i++) {
        if (allow_refs && (txn[i].kind & TXN_REUSE_DATA)) has_reuse = 1;
        uint64_t size = allow_refs ? txn[i].size : reqs[i].size;
        if (size == 0 || size > MAX_SIZE) continue;
        if (declared > MAX_BATCH_BYTES - size) return -1;
        declared += size;
    }
    size_t header_size = sizeof(uint64_t) + (size_t)n * sizeof(int64_t);
    if (header_size > SIZE_MAX - (size_t)declared) return -1;
    uint8_t *response = (uint8_t *)malloc(header_size + (size_t)declared);
    uint64_t *result_offsets = (uint64_t *)calloc((size_t)n, sizeof(uint64_t));
    size_t reuse_cap = 1;
    while (reuse_cap < n * 2) reuse_cap <<= 1;
    uint32_t *reuse_slots = has_reuse ? (uint32_t *)calloc(reuse_cap, sizeof(uint32_t)) : NULL;
    uint64_t *result_addresses = has_reuse ? (uint64_t *)calloc((size_t)n, sizeof(uint64_t)) : NULL;
    if (!response || !result_offsets || (has_reuse && (!reuse_slots || !result_addresses))) {
        free(response);
        free(result_offsets);
        free(reuse_slots);
        free(result_addresses);
        return -1;
    }
    int64_t *lengths = (int64_t *)(response + sizeof(uint64_t));
    memcpy(response, &n, sizeof(n));
    uint64_t payload_used = 0;

    for (uint64_t i = 0; i < n; i++) {
        uint64_t addr = 0;
        uint64_t size = allow_refs ? txn[i].size : reqs[i].size;
        uint32_t kind = allow_refs ? txn[i].kind & ~TXN_REUSE_DATA : TXN_DIRECT;
        /* Explicit opt-in for resident data only. Pointer/identity validation,
         * standalone transactions and guards retain fresh pread semantics. */
        int reuse = allow_refs && (txn[i].kind & TXN_REUSE_DATA)
            && (kind == TXN_DIRECT || kind == TXN_DEREF || kind == TXN_LIST_ITEMS);
        int invalid = (size == 0 || size > MAX_SIZE);
        if (!invalid && !allow_refs) {
            addr = reqs[i].addr;
        } else if (!invalid && kind == TXN_DIRECT) {
            if (txn[i].value <= 0) invalid = 1;
            addr = (uint64_t)txn[i].value;
        } else if (!invalid && kind == TXN_DEREF) {
            uint32_t ref = txn[i].ref;
            int64_t off = txn[i].offset;
            if (ref >= i || lengths[ref] <= 0 || off < 0
                    || (uint64_t)off + sizeof(uint64_t) > (uint64_t)lengths[ref]) {
                invalid = 1;
            } else {
                uint64_t base = 0;
                memcpy(&base, response + result_offsets[ref] + (size_t)off,
                       sizeof(base));
                if (!base || checked_add_signed(base, txn[i].value, &addr) < 0)
                    invalid = 1;
            }
        } else if (!invalid && kind == TXN_LIST_ITEMS) {
            uint32_t ref = txn[i].ref;
            uint32_t pointer_off = (uint32_t)(uint64_t)txn[i].offset;
            uint32_t count_off = (uint32_t)((uint64_t)txn[i].offset >> 32);
            if (ref >= i || lengths[ref] <= 0 || size % sizeof(uint64_t)
                    || txn[i].value != IL2CPP_ARRAY_ITEMS
                    || (uint64_t)pointer_off + 8 > (uint64_t)lengths[ref]
                    || (uint64_t)count_off + 4 > (uint64_t)lengths[ref]) {
                invalid = 1;
            } else {
                uint64_t array_ptr = 0, length_addr = 0;
                int32_t count = -1;
                uint32_t capacity = 0;
                const uint8_t *source = response + result_offsets[ref];
                memcpy(&array_ptr, source + pointer_off, 8);
                memcpy(&count, source + count_off, 4);
                if (count < 0 || (uint64_t)count > size / 8) invalid = 1;
                else if (!count) size = 0;
                else if (!array_ptr
                        || checked_add_signed(array_ptr, IL2CPP_ARRAY_MAX_LENGTH,
                                              &length_addr) < 0
                        || read_u32_at(fd, length_addr, &capacity) < 0
                        || capacity > MAX_ARRAY_LENGTH || (uint32_t)count > capacity
                        || checked_add_signed(array_ptr, IL2CPP_ARRAY_ITEMS, &addr) < 0
                        || addr > UINT64_MAX - (uint64_t)count * 8) invalid = 1;
                else size = (uint64_t)count * 8;
            }
        } else if (!invalid && (kind == TXN_ARRAY_DEREF
                                || kind == TXN_ARRAY_PTR)) {
            uint32_t ref = txn[i].ref;
            uint64_t packed_offsets = (uint64_t)txn[i].offset;
            uint32_t array_off = (uint32_t)(packed_offsets & 0xFFFFFFFFULL);
            uint32_t index_off = (uint32_t)(packed_offsets >> 32);
            if ((kind == TXN_ARRAY_PTR && size != sizeof(uint64_t))
                    || ref >= i || lengths[ref] <= 0
                    || (uint64_t)array_off + sizeof(uint64_t)
                        > (uint64_t)lengths[ref]
                    || (uint64_t)index_off + sizeof(int32_t)
                        > (uint64_t)lengths[ref]) {
                invalid = 1;
            } else {
                uint64_t array_ptr = 0;
                uint32_t max_length = 0;
                int32_t index = -1;
                const uint8_t *source = response + result_offsets[ref];
                memcpy(&array_ptr, source + array_off, sizeof(array_ptr));
                memcpy(&index, source + index_off, sizeof(index));
                uint64_t length_addr = 0;
                if (!array_ptr || index < 0
                        || checked_add_signed(array_ptr,
                                              (int64_t)IL2CPP_ARRAY_MAX_LENGTH,
                                              &length_addr) < 0
                        /* IL2CPP max_length 是 int32/u32；+0x1C 是填充，
                         * 不能按 u64 读取并把填充垃圾并入数组长度。 */
                        || read_u32_at(fd, length_addr, &max_length) < 0
                        || max_length > MAX_ARRAY_LENGTH
                        || (uint64_t)index >= max_length) {
                    invalid = 1;
                } else {
                    uint64_t item_offset = (uint64_t)index * sizeof(uint64_t);
                    uint64_t item_addr = 0;
                    if (array_ptr > UINT64_MAX - IL2CPP_ARRAY_ITEMS
                            || array_ptr + IL2CPP_ARRAY_ITEMS
                                > UINT64_MAX - item_offset) {
                        invalid = 1;
                    } else {
                        item_addr = array_ptr + IL2CPP_ARRAY_ITEMS + item_offset;
                        if (kind == TXN_ARRAY_PTR) {
                            addr = item_addr;
                        } else {
                            uint64_t object_ptr = 0;
                            if (read_u64_at(fd, item_addr, &object_ptr) < 0
                                    || !object_ptr
                                    || checked_add_signed(object_ptr,
                                                          txn[i].value,
                                                          &addr) < 0)
                                invalid = 1;
                        }
                    }
                }
            }
        } else if (!invalid) {
            invalid = 1;
        }

        result_offsets[i] = (uint64_t)header_size + payload_used;
        if (invalid) {
            lengths[i] = -EINVAL;
            continue;
        }
        if (!size) {
            lengths[i] = 0;
            continue;
        }
        size_t slot = (size_t)(((addr >> 3) ^ (size * 0x9E3779B97F4A7C15ULL))
                              & (reuse_cap - 1));
        int reused = 0;
        if (reuse) {
            while (reuse_slots[slot]) {
                uint32_t prior = reuse_slots[slot] - 1;
                if (result_addresses[prior] == addr && lengths[prior] == (int64_t)size) {
                    memcpy(response + header_size + payload_used,
                           response + result_offsets[prior], (size_t)size);
                    lengths[i] = (int64_t)size;
                    payload_used += size;
                    reused = 1;
                    break;
                }
                slot = (slot + 1) & (reuse_cap - 1);
            }
        }
        if (reused) continue;
        ssize_t r;
        do {
            r = pread(fd, response + header_size + payload_used,
                      (size_t)size, (off_t)addr);
        } while (r < 0 && errno == EINTR);
        /* A short variable-length array must not masquerade as a smaller
         * valid list. Its descendants must fail too. Do not publish padding. */
        if (allow_refs && kind == TXN_LIST_ITEMS && r != (ssize_t)size) {
            lengths[i] = r < 0 ? -(int64_t)errno : -EIO;
            continue;
        }
        lengths[i] = r < 0 ? -(int64_t)errno : (int64_t)r;
        if (r > 0) payload_used += (uint64_t)r;
        if (reuse && r == (ssize_t)size) {
            result_addresses[i] = addr;
            reuse_slots[slot] = (uint32_t)i + 1;
        }
    }

    free(result_offsets);
    free(reuse_slots);
    free(result_addresses);
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

typedef struct {
    uint64_t meta[3];
    uint8_t *data;
    size_t size;
} CaptureResponse;

/* Independent guards/retries; no bytes or validity shared between domains.
 * Caller owns the result even on failure. No response is sent here. */
static int capture_guarded_response(int fd, const TxnReq *ops, uint64_t count,
        uint64_t guard_addr, uint32_t guard_size, uint32_t attempts,
        CaptureResponse *out) {
    for (uint32_t i = 0; i < attempts; i++) {
        free(out->data);
        out->data = NULL;
        out->size = 0;
        out->meta[0] = i + 1;
        out->meta[1] = read_guard_value(fd, guard_addr, guard_size);
        if (build_packed_response(fd, NULL, count, 1, ops,
                                 &out->data, &out->size) < 0) return -1;
        out->meta[2] = read_guard_value(fd, guard_addr, guard_size);
        if (out->meta[1] != UINT64_MAX && out->meta[1] == out->meta[2]) break;
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

    if (write_exact(1, "AKMSRV5\n", 8) < 0) return 4;

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

        if (n == GUARDED_TXN_MAGIC) {
            uint64_t header[2];
            uint32_t options[2];
            if (read_exact(0, header, sizeof(header)) < 0) return 0;
            if (read_exact(0, options, sizeof(options)) < 0) return 0;
            uint64_t count = header[0];
            uint64_t guard_addr = header[1];
            uint32_t guard_size = options[0];
            uint32_t max_attempts = options[1];
            if (count == 0 || count > MAX_REQ) return 26;
            if ((guard_addr && guard_size != 4 && guard_size != 8)
                    || (!guard_addr && guard_size != 0)) return 27;
            if (max_attempts < 1) max_attempts = 1;
            if (max_attempts > MAX_GUARD_ATTEMPTS)
                max_attempts = MAX_GUARD_ATTEMPTS;
            TxnReq *txn = (TxnReq *)malloc((size_t)count * sizeof(TxnReq));
            if (!txn) return 28;
            if (read_exact(0, txn, (size_t)count * sizeof(TxnReq)) < 0) {
                free(txn);
                return 0;
            }
            uint8_t *response = NULL;
            size_t response_size = 0;
            uint64_t attempts = 0;
            uint64_t guard_start = UINT64_MAX, guard_end = UINT64_MAX;
            for (uint32_t attempt = 0; attempt < max_attempts; attempt++) {
                free(response);
                response = NULL;
                response_size = 0;
                guard_start = read_guard_value(fd, guard_addr, guard_size);
                if (build_packed_response(fd, NULL, count, 1, txn,
                                          &response, &response_size) < 0) {
                    free(txn);
                    free(response);
                    return 29;
                }
                guard_end = read_guard_value(fd, guard_addr, guard_size);
                attempts = (uint64_t)attempt + 1;
                if (!guard_addr || (guard_start != UINT64_MAX
                        && guard_start == guard_end)) break;
            }
            free(txn);
            uint64_t meta[3] = { attempts, guard_start, guard_end };
            if (write_exact(1, meta, sizeof(meta)) < 0
                    || write_exact(1, response, response_size) < 0) {
                free(response);
                return 30;
            }
            free(response);
            continue;
        }

        if (n == PLAN_UPLOAD_MAGIC) {
            uint64_t header[2];
            uint32_t options[2];
            if (read_exact(0, header, sizeof(header)) < 0) return 0;
            if (read_exact(0, options, sizeof(options)) < 0) return 0;
            uint64_t count = header[0];
            if (count == 0 || count > MAX_REQ) return 18;
            if ((header[1] && options[0] != 4 && options[0] != 8)
                    || (!header[1] && options[0] != 0)) return 19;
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
            if (saved_max_attempts > MAX_GUARD_ATTEMPTS)
                saved_max_attempts = MAX_GUARD_ATTEMPTS;
            if (write_exact(1, &saved_plan_count, sizeof(saved_plan_count)) < 0)
                return 21;
            continue;
        }

        /* Extension: resident core followed immediately by one optional domain.
         * Input: count + TxnReq[count]. Optional uses the same frame address,
         * one attempt. Both complete before ANY response write; two ordinary
         * guarded responses follow, retaining independent failure semantics. */
        if (n == COORDINATED_EXEC_MAGIC) {
            uint64_t count = 0;
            if (!saved_plan || !saved_plan_count || !saved_guard_addr
                    || saved_guard_size != 4) return 30;
            if (read_exact(0, &count, sizeof(count)) < 0) return 0;
            if (!count || count > MAX_REQ) return 31;
            TxnReq *ops = malloc((size_t)count * sizeof(TxnReq));
            if (!ops) return 32;
            if (read_exact(0, ops, (size_t)count * sizeof(TxnReq)) < 0) {
                free(ops);
                return 0;
            }
            CaptureResponse core = {0}, optional = {0};
            int rc = capture_guarded_response(fd, saved_plan, saved_plan_count,
                saved_guard_addr, saved_guard_size, saved_max_attempts, &core);
            if (!rc) rc = capture_guarded_response(fd, ops, count,
                saved_guard_addr, saved_guard_size, 1, &optional);
            free(ops);
            if (!rc) rc = write_exact(1, core.meta, sizeof(core.meta));
            if (!rc) rc = write_exact(1, core.data, core.size);
            if (!rc) rc = write_exact(1, optional.meta, sizeof(optional.meta));
            if (!rc) rc = write_exact(1, optional.data, optional.size);
            free(core.data);
            free(optional.data);
            if (rc < 0) return 33;
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
