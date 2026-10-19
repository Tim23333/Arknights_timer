/* Run the production C reader against this test process's own memory only. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

static int reads;
static volatile uint32_t *changing_guard;
static ssize_t counted_pread(int fd, void *data, size_t size, off_t offset) {
    ++reads;
    ssize_t result = pread(fd, data, size, offset);
    if (changing_guard && (uint64_t)offset == (uint64_t)(uintptr_t)changing_guard)
        ++*changing_guard;
    return result;
}
#define pread counted_pread
#define main production_memsrv_main
#include "memsrv.c"
#undef main
#undef pread

static int failures;
static void check(const char *name, int ok) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) ++failures;
}
static void put64(void *data, size_t offset, uint64_t value) { memcpy((char *)data + offset, &value, 8); }
static void put32(void *data, size_t offset, int32_t value) { memcpy((char *)data + offset, &value, 4); }
static int64_t length_at(const uint8_t *response, int index) {
    int64_t length; memcpy(&length, response + 8 + index * 8, 8); return length;
}
static uint64_t item_at(const uint8_t *response, int index) {
    uint64_t count, value; memcpy(&count, response, 8);
    size_t offset = 8 + count * 8;
    for (int i = 0; i < index; ++i) if (length_at(response, i) > 0) offset += length_at(response, i);
    memcpy(&value, response + offset, 8); return value;
}
static uint8_t *capture(int fd, TxnReq *ops, int count) {
    uint8_t *response = NULL; size_t size = 0;
    if (build_packed_response(fd, NULL, count, 1, ops, &response, &size)) return NULL;
    return response;
}
static TxnReq direct(void *address, uint64_t size) {
    return (TxnReq){TXN_DIRECT, 0, (int64_t)(uintptr_t)address, 0, size};
}
static void coordinated_case(const char *name, int invalid_optional) {
    static uint64_t core_value = 123, optional_value = 456;
    static uint32_t guard = 42;
    int input[2], output[2];
    if (pipe(input) || pipe(output)) { check(name, 0); return; }
    pid_t child = fork();
    if (!child) {
        dup2(input[0], 0); dup2(output[1], 1);
        close(input[0]); close(input[1]); close(output[0]); close(output[1]);
        char pid[32]; snprintf(pid, sizeof(pid), "%d", getpid());
        char *args[] = {"native-reader", pid, NULL};
        _exit(production_memsrv_main(2, args));
    }
    close(input[0]); close(output[1]);
    char banner[8]; uint64_t acknowledgement = 0;
    int ok = child > 0 && read_exact(output[0], banner, 8) == 0 && !memcmp(banner, "AKMSRV5\n", 8);
    uint64_t upload[] = {PLAN_UPLOAD_MAGIC, 1, (uint64_t)(uintptr_t)&guard};
    uint32_t options[] = {4, 3};
    TxnReq core = direct(&core_value, 8);
    ok = ok && write_exact(input[1], upload, sizeof(upload)) == 0
        && write_exact(input[1], options, sizeof(options)) == 0
        && write_exact(input[1], &core, sizeof(core)) == 0
        && read_exact(output[0], &acknowledgement, 8) == 0 && acknowledgement == 1;
    uint64_t command[] = {COORDINATED_EXEC_MAGIC, 1};
    TxnReq optional = direct(invalid_optional ? NULL : &optional_value, 8);
    ok = ok && write_exact(input[1], command, sizeof(command)) == 0
        && write_exact(input[1], &optional, sizeof(optional)) == 0;
    uint64_t meta[3] = {0}, count = 0, value = 0; int64_t length = 0;
    ok = ok && read_exact(output[0], meta, sizeof(meta)) == 0 && meta[0] == 1
        && meta[1] == 42 && meta[2] == 42
        && read_exact(output[0], &count, 8) == 0 && count == 1
        && read_exact(output[0], &length, 8) == 0 && length == 8
        && read_exact(output[0], &value, 8) == 0 && value == core_value;
    ok = ok && read_exact(output[0], meta, sizeof(meta)) == 0 && meta[0] == 1
        && meta[1] == 42 && meta[2] == 42
        && read_exact(output[0], &count, 8) == 0 && count == 1
        && read_exact(output[0], &length, 8) == 0;
    if (invalid_optional) ok = ok && length < 0;
    else ok = ok && length == 8 && read_exact(output[0], &value, 8) == 0 && value == optional_value;
    close(input[1]); close(output[0]);
    int status = 0; waitpid(child, &status, 0);
    if (!ok || !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        fprintf(stderr, "DIAG %s ok=%d status=%d ack=%llu length=%lld count=%llu meta=%llu/%llu/%llu value=%llu\n",
            name, ok, status, (unsigned long long)acknowledgement, (long long)length,
            (unsigned long long)count, (unsigned long long)meta[0], (unsigned long long)meta[1],
            (unsigned long long)meta[2], (unsigned long long)value);
    check(name, ok && WIFEXITED(status) && WEXITSTATUS(status) == 0);
}

int main(void) {
    int fd = open("/proc/self/mem", O_RDONLY);
    if (fd < 0) return 90;
    uint64_t value = 0x12345678, pointer = (uint64_t)(uintptr_t)&value;
    TxnReq ops[3] = {direct(&value, 8)};
    uint8_t *result = capture(fd, ops, 1);
    check("direct", result && length_at(result, 0) == 8 && item_at(result, 0) == value); free(result);
    ops[0] = direct(NULL, 8); result = capture(fd, ops, 1);
    check("invalid_pointer", result && length_at(result, 0) < 0); free(result);
    ops[0] = direct(&value, 0); result = capture(fd, ops, 1);
    check("invalid_size", result && length_at(result, 0) < 0); free(result);
    ops[0] = direct(&pointer, 8); ops[1] = (TxnReq){TXN_DEREF, 0, 0, 0, 8};
    result = capture(fd, ops, 2);
    check("parent_dereference", result && item_at(result, 1) == value); free(result);
    ops[1].ref = 1; result = capture(fd, ops, 2);
    check("forward_reference_rejected", result && length_at(result, 1) < 0); free(result);

    uint8_t array[0x40] = {0}, header[0x20] = {0};
    put32(array, 0x18, 4); put64(array, 0x20, 101); put64(array, 0x28, 202);
    put64(array, 0x30, 303); put64(array, 0x38, 404);
    put64(header, 0x10, (uint64_t)(uintptr_t)array); put32(header, 0x18, 2);
    ops[0] = direct(header, sizeof(header));
    ops[1] = (TxnReq){TXN_LIST_ITEMS, 0, 0x20, ((int64_t)0x18 << 32) | 0x10, 32};
    result = capture(fd, ops, 2);
    check("list_current_count", result && length_at(result, 1) == 16 && item_at(result, 1) == 101); free(result);
    put32(header, 0x18, 0); result = capture(fd, ops, 2);
    check("list_zero_count", result && length_at(result, 1) == 0); free(result);
    put32(header, 0x18, 4); result = capture(fd, ops, 2);
    check("list_grows_without_reupload", result && length_at(result, 1) == 32); free(result);
    put32(header, 0x18, -1); result = capture(fd, ops, 2);
    check("negative_count_rejected", result && length_at(result, 1) < 0); free(result);
    put32(header, 0x18, 5); result = capture(fd, ops, 2);
    check("count_bound_rejected", result && length_at(result, 1) < 0); free(result);
    put32(header, 0x18, 4); put32(array, 0x18, 3); result = capture(fd, ops, 2);
    check("capacity_rejected", result && length_at(result, 1) < 0); free(result);
    put32(array, 0x18, 0x7fffffff); result = capture(fd, ops, 2);
    check("oversized_capacity_rejected", result && length_at(result, 1) < 0); free(result);
    put32(array, 0x18, 4); ops[1].offset = ((int64_t)0x18 << 32) | 0x30;
    result = capture(fd, ops, 2);
    check("header_bounds_rejected", result && length_at(result, 1) < 0); free(result);
    ops[1].offset = ((int64_t)0x18 << 32) | 0x10;
    size_t page = sysconf(_SC_PAGESIZE);
    uint8_t *region = mmap(NULL, page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (region == MAP_FAILED) return 91;
    munmap(region + page, page);
    uint8_t *short_array = region + page - 0x28;
    put32(short_array, 0x18, 4); put64(short_array, 0x20, 101);
    put64(header, 0x10, (uint64_t)(uintptr_t)short_array);
    result = capture(fd, ops, 2);
    check("short_list_rejected", result && length_at(result, 1) < 0); free(result);
    munmap(region, page);

    ops[0] = direct(&value, 8); ops[0].kind |= TXN_REUSE_DATA; ops[1] = ops[0]; reads = 0;
    result = capture(fd, ops, 2);
    check("same_transaction_reuse", result && reads == 1 && item_at(result, 1) == value); free(result);
    ops[0].kind = TXN_DIRECT; ops[1] = ops[0]; reads = 0;
    result = capture(fd, ops, 2);
    check("ordinary_reads_remain_fresh", result && reads == 2); free(result);
    ops[0].kind |= TXN_REUSE_DATA; ops[1] = ops[0]; ops[1].size = 4; reads = 0;
    result = capture(fd, ops, 2);
    check("different_size_not_reused", result && reads == 2); free(result);
    ops[0] = direct(&value, 8); uint32_t guard = 42; CaptureResponse response = {0};
    int rc = capture_guarded_response(fd, ops, 1, (uint64_t)(uintptr_t)&guard, 4, 3, &response);
    check("stable_frame_accepted", rc == 0 && response.meta[0] == 1 && response.meta[1] == response.meta[2]); free(response.data);
    response = (CaptureResponse){0};
    changing_guard = &guard;
    rc = capture_guarded_response(fd, ops, 1, (uint64_t)(uintptr_t)&guard, 4, 3, &response);
    changing_guard = NULL;
    check("cross_frame_retry_bound", rc == 0 && response.meta[0] == 3 && response.meta[1] != response.meta[2]); free(response.data);
    close(fd);
    fflush(stdout);
    coordinated_case("coordinated_core_and_optional", 0);
    coordinated_case("optional_failure_preserves_core", 1);
    return failures ? 1 : 0;
}
