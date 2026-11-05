"""serve: run the web app and its API until Ctrl+C."""

import argparse

from .. import auth, db

THIS_COMPUTER = ("127.0.0.1", "localhost", "::1")


def run(args: argparse.Namespace) -> int:
    import uvicorn    # only here: loading the web server takes a moment

    print(f"Database: {db.describe()}")
    with db.connect() as session:       # also brings the tables up to date before the server starts
        if not auth.has_users(session):
            print("Accounts: none yet. Make one to log in with: python -m price_tracker user add NAME")
    if args.host not in THIS_COMPUTER:
        print("Warning:  other computers can reach it over plain HTTP, so passwords cross the network unencrypted.")
    print(f"Open:     http://{args.host}:{args.port}   (the API docs are at /docs). Ctrl+C stops it.")
    uvicorn.run("price_tracker.web:app", host=args.host, port=args.port, reload=args.reload)
    return 0
