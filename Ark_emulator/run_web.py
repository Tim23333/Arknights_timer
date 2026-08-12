"""Launch the Ark_emulator real-time web console."""

import argparse
import time
import webbrowser

from ark_emulator import Simulator
from ark_emulator.live_server import LiveServer


def main():
    parser = argparse.ArgumentParser(description="Ark_emulator web console")
    parser.add_argument("--level", default="level_main_01-01",
                        help="initial level id")
    parser.add_argument("--port", type=int, default=8794)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    sim = Simulator(level_id=args.level)
    server = LiveServer(sim, port=args.port, speed=1.0)
    try:
        server.start()
    except OSError as exc:
        raise SystemExit(
            "端口 %d 已被另一个网页模拟器占用，请先关闭旧窗口/进程，"
            "或使用 --port 指定其他端口。\n%s" % (args.port, exc))
    url = "http://127.0.0.1:%d/" % args.port
    print("Ark_emulator web console:", url)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
