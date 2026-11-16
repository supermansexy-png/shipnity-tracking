#!/usr/bin/env python3
"""
Shipnity CLI Tool for Hermes Agent
Supports reading orders, updating order/customer tags, and setting tracking numbers via Shipnity GraphQL API.
"""

import argparse
import datetime
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.shipnity.com"
GRAPHQL_URL = f"{BASE_URL}/api/graphql"
CSRF_URL = f"{BASE_URL}/get_csrf_token"


class ShipnityClient:
    def __init__(self, cookie_str: str = None):
        self.cookie_str = cookie_str or os.environ.get("SHIPNITY_COOKIE", "").strip()
        if not self.cookie_str:
            raise ValueError(
                "Missing SHIPNITY_COOKIE environment variable. "
                "Please set SHIPNITY_COOKIE='remember_user_token=...; _shipnity_session=...'"
            )
        self.csrf_token = None

    def _headers(self, include_csrf: bool = True) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/order/",
            "Cookie": self.cookie_str,
        }
        if include_csrf and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

    def fetch_csrf_token(self) -> str:
        req = urllib.request.Request(CSRF_URL, headers=self._headers(include_csrf=False), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                # Update session cookie if server sent Set-Cookie
                set_cookies = resp.headers.get_all("Set-Cookie") or []
                self._merge_set_cookies(set_cookies)
                data = json.loads(resp.read().decode("utf-8"))
                self.csrf_token = data.get("csrf_token")
                if not self.csrf_token:
                    raise RuntimeError(f"Failed to get csrf_token from {CSRF_URL}: {data}")
                return self.csrf_token
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} when fetching CSRF token: {body}") from e

    def _merge_set_cookies(self, set_cookies: list):
        if not set_cookies:
            return
        cookie_map = {}
        for part in self.cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookie_map[k.strip()] = v.strip()
        for sc in set_cookies:
            first_pair = sc.split(";", 1)[0]
            if "=" in first_pair:
                k, v = first_pair.strip().split("=", 1)
                cookie_map[k.strip()] = v.strip()
        self.cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_map.items())

    def graphql(self, query: str, variables: dict = None) -> dict:
        if not self.csrf_token:
            self.fetch_csrf_token()
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=self._headers(include_csrf=True), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} from GraphQL API: {body}") from e

    def list_orders(self, status: str = "READY_TO_SHIP", limit: int = 50, search: str = None) -> list:
        query = """
        query orderList($first: Int, $query: OrderQueryInput, $filter: OrderFilterInput) {
          orderList(first: $first, query: $query, filter: $filter) {
            edges {
              node {
                id
                slug
                invoiceNumber
                status
                currentStateForm
                tag
                closedNote
                closedCost
                closedAt
                shippingType
                shippop
                price
                shippingFee
                paidAmount
                unpaidAmount
                createdAt
                customer {
                  id
                  name
                  tel
                  address
                  tags
                }
                purchases {
                  id
                  name
                  quantity
                  price
                }
              }
            }
          }
        }
        """
        q_input = {"status": status, "sort": "CREATED_AT_DESC"}
        if search:
            q_input["search"] = search

        res = self.graphql(query, {"first": limit, "query": q_input, "filter": {}})
        edges = (((res.get("data") or {}).get("orderList") or {}).get("edges")) or []
        return [edge["node"] for edge in edges if edge and edge.get("node")]

    def set_tracking(
        self,
        order_id: str,
        tracking_number: str,
        shipping_cost: float = 0.0,
        close_order: bool = True,
        send_auto_message: bool = False,
    ) -> dict:
        if close_order:
            mutation = """
            mutation closeOrder($input: CloseOrderInput!) {
              closeOrder(input: $input) {
                order {
                  id
                  invoiceNumber
                  status
                  closedNote
                  closedCost
                  closedAt
                }
                errors
              }
            }
            """
            tz_th = datetime.timezone(datetime.timedelta(hours=7))
            now_iso = datetime.datetime.now(tz_th).isoformat(timespec="seconds")
            variables = {
                "input": {
                    "id": str(order_id),
                    "closedNote": tracking_number.strip(),
                    "closedCost": float(shipping_cost),
                    "closedAt": now_iso,
                    "sendAutoMessage": bool(send_auto_message),
                }
            }
            return self.graphql(mutation, variables)
        else:
            mutation = """
            mutation updateOrder($input: UpdateOrderInput!) {
              updateOrder(input: $input) {
                order {
                  id
                  invoiceNumber
                  status
                  closedNote
                }
                errors
              }
            }
            """
            variables = {
                "input": {
                    "id": str(order_id),
                    "closedNote": tracking_number.strip(),
                }
            }
            return self.graphql(mutation, variables)

    def set_order_tag(self, order_id: str, tag: str) -> dict:
        mutation = """
        mutation updateOrder($input: UpdateOrderInput!) {
          updateOrder(input: $input) {
            order {
              id
              invoiceNumber
              tag
            }
            errors
          }
        }
        """
        variables = {"input": {"id": str(order_id), "tag": tag.strip()}}
        return self.graphql(mutation, variables)

    def set_customer_tags(self, customer_id: str, tags: list) -> dict:
        mutation = """
        mutation updateCustomer($input: UpdateCustomerInput!) {
          updateCustomer(input: $input) {
            customer {
              id
              name
              tags
            }
            errors
          }
        }
        """
        variables = {"input": {"id": str(customer_id), "tags": tags}}
        return self.graphql(mutation, variables)


def main():
    parser = argparse.ArgumentParser(description="Shipnity Order & Tracking CLI for Hermes AI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    p_list = subparsers.add_parser("list", help="List orders from Shipnity")
    p_list.add_argument(
        "--status",
        default="READY_TO_SHIP",
        help="Order status filter: READY_TO_SHIP, ALL, TRANSFER, CLOSE, etc. (default: READY_TO_SHIP)",
    )
    p_list.add_argument("--limit", type=int, default=50, help="Number of orders to fetch (default: 50)")
    p_list.add_argument("--search", default=None, help="Optional search keyword (invoice, name, phone, slug)")

    # set-tracking command
    p_track = subparsers.add_parser("set-tracking", help="Set tracking number (closedNote) on an order")
    p_track.add_argument("--order-id", required=True, help="Internal Order ID (e.g. 136430164)")
    p_track.add_argument("--tracking", required=True, help="Tracking number (e.g. TH0123456789A)")
    p_track.add_argument("--cost", type=float, default=0.0, help="Actual shipping cost (default: 0.0)")
    p_track.add_argument(
        "--mode",
        choices=["close", "update"],
        default="close",
        help="'close' transitions order to shipped (closeOrder); 'update' only edits closedNote (updateOrder)",
    )
    p_track.add_argument(
        "--notify",
        action="store_true",
        help="Send automatic chat notification to customer when closing order",
    )

    # set-tag command
    p_tag = subparsers.add_parser("set-tag", help="Set order tag or customer tags")
    p_tag.add_argument("--order-id", help="Internal Order ID to update order tag")
    p_tag.add_argument("--tag", help="Order tag string")
    p_tag.add_argument("--customer-id", help="Customer ID to update customer tags")
    p_tag.add_argument("--customer-tags", help="Comma-separated customer tags (e.g. 'VIP,ส่งแล้ว')")

    args = parser.parse_args()

    try:
        client = ShipnityClient()
        if args.command == "list":
            orders = client.list_orders(status=args.status, limit=args.limit, search=args.search)
            print(json.dumps({"ok": True, "count": len(orders), "orders": orders}, ensure_ascii=False, indent=2))

        elif args.command == "set-tracking":
            close_mode = args.mode == "close"
            res = client.set_tracking(
                order_id=args.order_id,
                tracking_number=args.tracking,
                shipping_cost=args.cost,
                close_order=close_mode,
                send_auto_message=args.notify,
            )
            print(json.dumps({"ok": True, "result": res}, ensure_ascii=False, indent=2))

        elif args.command == "set-tag":
            if args.order_id and args.tag is not None:
                res = client.set_order_tag(order_id=args.order_id, tag=args.tag)
                print(json.dumps({"ok": True, "result": res}, ensure_ascii=False, indent=2))
            elif args.customer_id and args.customer_tags is not None:
                tags_list = [t.strip() for t in args.customer_tags.split(",") if t.strip()]
                res = client.set_customer_tags(customer_id=args.customer_id, tags=tags_list)
                print(json.dumps({"ok": True, "result": res}, ensure_ascii=False, indent=2))
            else:
                parser.error("Provide either (--order-id and --tag) OR (--customer-id and --customer-tags)")

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
