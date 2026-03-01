import sys
from src.cli.cli import cli
from src.cli.shell import shell

def main():
    if len(sys.argv) == 1:
        shell()
    else:
        cli()

if __name__ == "__main__":
    main()