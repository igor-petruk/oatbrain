import sys
from oatbrain.app.bootstrap import build_app


def main() -> int:
    app, filtered_argv = build_app(sys.argv)
    return int(app.run(filtered_argv))


if __name__ == "__main__":
    sys.exit(main())
