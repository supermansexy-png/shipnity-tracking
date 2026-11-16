#!/usr/bin/env python3
"""
Shipnity CLI Tool for Hermes Agent (Verified against live Shipnity GraphQL Schema)
Supports:
- Authentication via SHIPNITY_COOKIE or (SHIPNITY_EMAIL + SHIPNITY_PASSWORD)
- Listing & searching orders (orderList -> nodes)
- Closing orders & setting tracking numbers (closeOrder -> closedNote)
- Updating order tags or tracking numbers (updateOrder -> tag, closedNote)
- Updating customer tags (updateCustomer -> tags)
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.shipnity.com"
GRAPHQL_URL = f"{BASE_URL}/api/graphql"
CSRF_URL = f"{BASE_URL}/get_csrf_token"

ORDER_LIST_QUERY = """
query (
  $perPage: Int
  $page: Int
  $ids: [ID!]
  $search: String
) {
  orderList(
    perPage: $perPage
    page: $page
    ids: $ids
    search: $search
  ) {
    nodesCount
    pagesCount
    hasNextPage
    nodes {
      id
      invoiceNumber
      slug
      name
      tel
      address
      districtCode
      price
      shippingFee
      paidAmount
      unpaidAmount
      status
      closed
      canClose
      closedNote
      shippingType
      shippop
      tag
      createdAt
      customer {
        id
        name
        email
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
"""

CLOSE_ORDER_MUTATION = """
mutation ($input: CloseOrderInput!) {
  closeOrder(input: $input) {
    order {
      id
      invoiceNumber
      closed
      closedNote
      status
    }
    errors
  }
}
"""

UPDATE_ORDER_MUTATION = """
mutation ($input: UpdateOrderInput!) {
  updateOrder(input: $input) {
    order {
      id
      invoiceNumber
      tag
      closedNote
      status
    }
    errors
  }
}
"""

UPDATE_CUSTOMER_MUTATION = """
mutation ($input: UpdateCustomerInput!) {
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

SIGN_IN_MUTATION = """
mutation ($input: SignInUserInput!) {
  signInUser(input: $input) {
    user {
      id
    }
    errors
  }
}
"""


class ShipnityClient:
    def __init__(self, cookie_str: str = None, email: str = None, password: str = None):
        self.cookie_str = (cookie_str or os.environ.get("SHIPNITY_COOKIE", "")).strip()
        self.email = (email or os.environ.get("SHIPNITY_EMAIL", "")).strip()
        self.password = (password or os.environ.get("SHIPNITY_PASSWORD", "")).strip()
        if not self.cookie_str and not (self.email and self.password):
            raise ValueError(
                "Missing credentials. Set SHIPNITY_COOKIE='remember_user_token=...; _shipnity_session=...' "
                "or set both SHIPNITY_EMAIL and SHIPNITY_PASSWORD."
            )
        self.csrf_token = None

    def _headers(self, include_csrf: bool = True, referer: str = f"{BASE_URL}/order/") -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": BASE_URL,
            "Referer": referer,
        }
        if self.cookie_str:
            headers["Cookie"] = self.cookie_str
        if include_csrf and self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

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

    def fetch_csrf_token(self) -> str:
        req = urllib.request.Request(CSRF_URL, headers=self._headers(include_csrf=False), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                set_cookies = resp.headers.get_all("Set-Cookie") or []
                self._merge_set_cookies(set_cookies)
                data = json.loads(resp.read().decode("utf-8"))
                # Shipnity /get_csrf_token returns {"token": "..."}
                self.csrf_token = data.get("token") or data.get("csrf_token")
                if not self.csrf_token:
                    raise RuntimeError(f"Failed to extract token from {CSRF_URL}: {data}")
                return self.csrf_token
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} when fetching CSRF token: {body}") from e

    def login_if_needed(self):
        if not self.csrf_token:
            self.fetch_csrf_token()
        if not self.cookie_str and self.email and self.password:
            payload = json.dumps(
                {
                    "operationName": None,
                    "variables": {"input": {"email": self.email, "password": self.password}},
                    "query": SIGN_IN_MUTATION,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                GRAPHQL_URL,
                data=payload,
                headers=self._headers(include_csrf=True, referer=f"{BASE_URL}/authen/"),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                set_cookies = resp.headers.get_all("Set-Cookie") or []
                self._merge_set_cookies(set_cookies)
                res_data = json.loads(resp.read().decode("utf-8"))
                errors = ((res_data.get("data") or {}).get("signInUser") or {}).get("errors")
                if errors:
                    raise RuntimeError(f"Login failed: {errors}")
            # Refresh CSRF token after login session change
            self.fetch_csrf_token()

    def graphql(self, query: str, variables: dict = None) -> dict:
        self.login_if_needed()
        payload = json.dumps({"operationName": None, "query": query, "variables": variables or {}}).encode("utf-8")
        req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=self._headers(include_csrf=True), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                set_cookies = resp.headers.get_all("Set-Cookie") or []
                self._merge_set_cookies(set_cookies)
                raw = resp.read().decode("utf-8")
                res = json.loads(raw)
                if res.get("errors"):
                    raise RuntimeError(f"GraphQL execution errors: {res['errors']}")
                return res
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} from GraphQL API: {body}") from e

    def list_orders(
        self,
        status: str = "ALL",
        limit: int = 50,
        page: int = 1,
        search: str = None,
        order_ids: list = None,
    ) -> dict:
        variables = {
            "perPage": int(limit),
            "page": int(page),
        }
        if search:
            variables["search"] = str(search).strip()
        if order_ids:
            variables["ids"] = [str(i).strip() for i in order_ids]

        res = self.graphql(ORDER_LIST_QUERY, variables)
        order_list_data = (res.get("data") or {}).get("orderList") or {}
        nodes = order_list_data.get("nodes") or []

        # Client-side filter if status specified (e.g. READY_TO_SHIP, CLOSE, TRANSFER, OPEN)
        if status and status.upper() != "ALL":
            target = status.upper()
            if target in ("READY_TO_SHIP", "UNCLOSED", "PENDING"):
                nodes = [
                    n
                    for n in nodes
                    if not n.get("closed")
                    and (n.get("status") in ("READY_TO_SHIP", "TRANSFER", "PACKING", "OPEN") or n.get("canClose"))
                ]
            else:
                nodes = [n for n in nodes if (n.get("status") or "").upper() == target]

        return {
            "total_in_query": order_list_data.get("nodesCount", len(nodes)),
            "count": len(nodes),
            "orders": nodes,
        }

    def set_tracking(
        self,
        order_id: str,
        tracking_number: str,
        shipping_cost: float = 0.0,
        close_order: bool = True,
        send_auto_message: bool = False,
    ) -> dict:
        if close_order:
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
            return self.graphql(CLOSE_ORDER_MUTATION, variables)
        else:
            variables = {
                "input": {
                    "id": str(order_id),
                    "closedNote": tracking_number.strip(),
                }
            }
            return self.graphql(UPDATE_ORDER_MUTATION, variables)

    def set_order_tag(self, order_id: str, tag: str) -> dict:
        variables = {"input": {"id": str(order_id), "tag": tag.strip()}}
        return self.graphql(UPDATE_ORDER_MUTATION, variables)

    def set_customer_tags(self, customer_id: str, tags: list) -> dict:
        variables = {"input": {"id": str(customer_id), "customerCategoryId": None, "tags": tags}}
        return self.graphql(UPDATE_CUSTOMER_MUTATION, variables)


def main():
    parser = argparse.ArgumentParser(description="Shipnity Order & Tracking CLI for Hermes AI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    p_list = subparsers.add_parser("list", help="List or search orders from Shipnity")
    p_list.add_argument(
        "--status",
        default="ALL",
        help="Filter by status: ALL, READY_TO_SHIP, CLOSE, TRANSFER, OPEN (default: ALL)",
    )
    p_list.add_argument("--limit", type=int, default=50, help="Number of orders per page (default: 50)")
    p_list.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    p_list.add_argument("--search", default=None, help="Search keyword (invoice e.g. DN92, customer name, tel)")
    p_list.add_argument("--id", default=None, help="Specific internal Order ID (e.g. 136430164)")

    # set-tracking command
    p_track = subparsers.add_parser("set-tracking", help="Set tracking number (closedNote) on an order")
    p_track.add_argument("--order-id", required=True, help="Internal Order ID (e.g. 136430164)")
    p_track.add_argument("--tracking", required=True, help="Tracking number (e.g. TH0123456789A)")
    p_track.add_argument("--cost", type=float, default=0.0, help="Actual shipping cost (default: 0.0)")
    p_track.add_argument(
        "--mode",
        choices=["close", "update"],
        default="close",
        help="'close' closes order & sets tracking (closeOrder); 'update' only edits closedNote (updateOrder)",
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
            ids = [args.id] if args.id else None
            data = client.list_orders(
                status=args.status,
                limit=args.limit,
                page=args.page,
                search=args.search,
                order_ids=ids,
            )
            print(json.dumps({"ok": True, **data}, ensure_ascii=False, indent=2))

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
