import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from risk_platform.config import get_settings
from risk_platform.database import engine
from risk_platform.market_data.connectors import (
    AlphaVantageConnector,
    EtfConnector,
    EtfListing,
    JsonFileConnector,
)
from risk_platform.market_data.repository import ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ETF snapshots into PostgreSQL.")
    parser.add_argument("path", nargs="?", type=Path, help="UTF-8 JSON ETF snapshot array")
    parser.add_argument("--alpha-vantage-symbol", metavar="TICKER")
    parser.add_argument("--exchange", help="Listing exchange code, preferably its MIC")
    parser.add_argument("--currency", help="Three-letter listing currency")
    parser.add_argument("--name", help="ETF display name (defaults to ticker)")
    args = parser.parse_args()
    connector: EtfConnector
    if args.alpha_vantage_symbol:
        if args.path or not args.exchange or not args.currency:
            parser.error("live imports require --exchange and --currency, and no JSON path")
        secret = get_settings().alpha_vantage_api_key
        if secret is None or not secret.get_secret_value():
            parser.error("set ALPHA_VANTAGE_API_KEY before a live import")
        listing = EtfListing(
            ticker=args.alpha_vantage_symbol.strip().upper(),
            exchange=args.exchange.strip().upper(),
            currency=args.currency.strip().upper(),
            name=args.name,
        )
        connector = AlphaVantageConnector(secret.get_secret_value(), listing)
    elif args.path:
        if args.exchange or args.currency or args.name:
            parser.error("listing options require --alpha-vantage-symbol")
        connector = JsonFileConnector(args.path)
    else:
        parser.error("provide a JSON path or --alpha-vantage-symbol")
    with Session(engine) as db, db.begin():
        ids = ingest(db, connector)
    print(json.dumps({"snapshot_ids": [str(value) for value in ids]}))


if __name__ == "__main__":
    main()
