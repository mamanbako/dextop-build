# dextop/cli.py
import argparse
import sys
import time

from dextop.orchestrator import ScrcpyOrchestrator, DisplayConfig, ConnectionConfig, SessionState


def main() -> int:
    parser = argparse.ArgumentParser(description="DeXtop — prototype CLI")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--app", help="Package à lancer dans l'écran virtuel, ex: com.android.settings")
    parser.add_argument("--serial", help="Serial ADB (USB ou IP:port)")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--list", action="store_true", help="Liste les appareils puis quitte")
    args = parser.parse_args()

    orch = ScrcpyOrchestrator(
        on_state_change=lambda s: print(f"[état] {s.value}"),
        on_log=lambda l: print(l),
    )

    if args.list:
        for dev in orch.list_devices():
            print(dev)
        return 0

    display = DisplayConfig(
        width=args.width,
        height=args.height,
        dpi=args.dpi,
        start_app=args.app,
    )
    connection = ConnectionConfig(
        serial=args.serial,
        audio=not args.no_audio,
    )

    try:
        orch.start(display, connection)
    except Exception as e:
        print(f"[erreur] {e}", file=sys.stderr)
        return 1

    try:
        # Attend la fin de la session (Ctrl+C pour arrêter)
        while orch.state in (SessionState.STARTING, SessionState.RUNNING):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dextop] Arrêt demandé…")
        orch.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())