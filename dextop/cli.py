import argparse
import sys
import time

from dextop.orchestrator import (
    ConnectionConfig,
    DisplayConfig,
    ScrcpyOrchestrator,
    SessionState,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeXtop — alternative open-source à Samsung DeX")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--app", help="Package Android à lancer")
    parser.add_argument("--serial", help="Appareil ADB (USB ou IP:port)")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--list", action="store_true", help="Lister les appareils puis quitter")
    args = parser.parse_args()

    orch = ScrcpyOrchestrator(
        on_state_change=lambda state: print(f"[état] {state.value}"),
        on_log=lambda line: print(line),
    )

    if args.list:
        devices = orch.list_devices()
        print("\n".join(devices) if devices else "Aucun appareil détecté")
        return 0

    display = DisplayConfig(
        width=args.width,
        height=args.height,
        dpi=args.dpi,
        start_app=args.app,
    )
    connection = ConnectionConfig(serial=args.serial, audio=not args.no_audio)

    try:
        orch.start(display, connection)
        while orch.state in (SessionState.STARTING, SessionState.RUNNING):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dextop] Arrêt demandé...")
        orch.stop()
    except Exception as exc:
        print(f"[erreur] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
