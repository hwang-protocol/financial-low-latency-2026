# 幂等作用域必须跨 TCP 重连保持稳定，所以用账户加交易日，不用连接级 session。
ACCOUNT = "ACCT-7"
TRADING_DAY = "2026-08-27"

# 同一个 ORD-1 提交三次：第二次内容相同，第三次数量被改过；ORD-2 是另一笔订单。
SUBMISSIONS = [
    ("ORD-1", {"symbol": "AAPL", "side": "BUY", "quantity": 10}),
    ("ORD-1", {"symbol": "AAPL", "side": "BUY", "quantity": 10}),
    ("ORD-1", {"symbol": "AAPL", "side": "BUY", "quantity": 99}),
    ("ORD-2", {"symbol": "AAPL", "side": "BUY", "quantity": 10}),
]


def submit(store, client_order_id, request):
    """幂等提交：返回响应和本次是否真的执行了业务动作（1 或 0）。"""
    key = (ACCOUNT, TRADING_DAY, client_order_id)
    if key in store:
        cached_request, cached_result = store[key]
        # 内容一致才允许重放；同键不同内容必须拒绝，不能把旧结果套给新请求。
        if cached_request == request:
            return "REPLAY:" + cached_result, 0
        return "CONFLICT", 0
    result = "ORDER_ACCEPTED"
    store[key] = (dict(request), result)
    return "NEW:" + result, 1


store = {}
action_count = 0
print("idempotency_scope=(%s,%s,client_order_id)" % (ACCOUNT, TRADING_DAY))
for client_order_id, request in SUBMISSIONS:
    response, executed = submit(store, client_order_id, request)
    action_count += executed
    print("submit id=%-5s quantity=%-3d response=%-22s action_count=%d"
          % (client_order_id, request["quantity"], response, action_count))
print("submissions=%d distinct_keys=%d action_count=%d"
      % (len(SUBMISSIONS), len(store), action_count))
