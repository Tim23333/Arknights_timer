// memsrv — 设备侧常驻内存读取服务 (明日方舟敌人监控)
//
// 由 nc -L 以 socket 作为 stdin/stdout 启动,  argv[1] 为目标 PID。
// 打开 /proc/<pid>/mem 一次, 之后每次读取仅一个 pread 系统调用,
// 替代每请求 fork+dd (~33ms), 把单请求压到 ~1ms。
//
// 协议 (全部小端):
//   启动: 写出 8 字节横幅 "AKMSRV1\n"
//   请求: u64 N, 随后 N 组 { u64 addr, u64 size }
//   响应: 每组 { i64 n, u8 data[n] };  n<0 表示 -errno, n<size 为短读
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

#define MAX_REQ 4096              // 单批最多请求数
#define MAX_SIZE (4 * 1024 * 1024)  // 单请求最大字节

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

int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);

    if (argc < 2) return 2;
    char path[64];
    snprintf(path, sizeof(path), "/proc/%s/mem", argv[1]);
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 3;

    if (write_exact(1, "AKMSRV1\n", 8) < 0) return 4;

    static uint8_t buf[MAX_SIZE];
    for (;;) {
        uint64_t n = 0;
        if (read_exact(0, &n, 8) < 0) return 0;   // EOF: 客户端断开
        if (n == 0) return 0;
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
