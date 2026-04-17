import sys
from oatbrain.app.bootstrap import build_app

def main() -> int:
    app = build_app(sys.argv)
    return int(app.run(sys.argv))

if __name__ == "__main__":
    sys.exit(main())
