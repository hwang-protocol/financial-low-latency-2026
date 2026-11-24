#!/usr/bin/env python3
"""Read-only end-of-chapter gate for the live SFC book shown by the gateway."""
import argparse
import json
import time
import urllib.request


def verify_state(state, profile="TRANSPORT"):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require((state['data_plane_mode'], state['data_plane_transition'],
             state['data_plane_owner']) == ('SFC', 'READY', 'sfc'), 'SFC not ready')
    require(state.get('experiment_profile', 'TRANSPORT') == profile, 'experiment profile mismatch')
    require(state['replay']['status'] == 'PLAYING', 'replay not playing')
    if profile == 'TRANSPORT':
        require(state['strategy']['enabled'] is False, 'Guardian strategy is enabled')
    else:
        require(state['health']['trader_manual']['status'] == 'ONLINE', 'manual trader not online')
    feed, receiver = state['feed'], state['feed_receiver']
    require(feed['integrity'] == 'HEALTHY' and feed['trading_gate'] == 'OPEN', 'feed not healthy/open')
    require(feed.get('availability') != 'STALE', 'feed is stale')
    require(feed['session'] == state['session'] and feed['next_expected'] > 0, 'feed session mismatch')
    for label, status in (('receiver', receiver), ('Guardian', state['health']['trader_auto'])):
        require(status['status'] == 'ONLINE', label + ' not online')
        require(0 <= state['server_ns'] - status['last_event_ns'] <= 4_000_000_000,
                label + ' heartbeat expired')
    require(receiver['clients'] >= 1, 'receiver has no consumer')
    for symbol in ('AAPL', 'NVDA'):
        book = state['trader_books'][symbol]
        require(book['session'] == state['session'], symbol + ' book session mismatch')
        require(book['integrity'] == 'HEALTHY' and book['trading_gate'] == 'OPEN', symbol + ' book not healthy')
        require(all(len(book[side]) == 5 and all(price > 0 and size > 0 for price, size in book[side])
                    for side in ('bids', 'asks')), symbol + ' five-level book missing')


def verify_progress(before, after, profile="TRANSPORT"):
    verify_state(before, profile)
    verify_state(after, profile)
    if before['session'] != after['session']:
        raise ValueError('session changed during sampling')
    pairs = {'feed': (before['feed']['next_expected'], after['feed']['next_expected']),
             'receiver': (before['feed_receiver']['received'], after['feed_receiver']['received'])}
    pairs.update({symbol: (before['trader_books'][symbol]['market_sequence'],
                           after['trader_books'][symbol]['market_sequence'])
                  for symbol in ('AAPL', 'NVDA')})
    if any(end <= start for start, end in pairs.values()):
        raise ValueError('receiver/feed/book sequence did not advance: ' + str(pairs))
    return {'result': 'LIVE_BOOK_READY', 'session': after['session'],
            'counters': pairs, 'before': before, 'after': after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('api')
    parser.add_argument('--timeout', type=float, default=25)
    parser.add_argument('--profile', choices=('TRANSPORT', 'SOFTWARE'), default='TRANSPORT')
    args = parser.parse_args()
    deadline, before, error = time.monotonic() + args.timeout, None, 'no sample'
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(args.api.rstrip('/') + '/api/state', timeout=3) as response:
                state = json.load(response)
            # Keep just the fields used by this gate, not order history/charts.
            state = {key: state[key] for key in (
                'data_plane_mode', 'data_plane_transition', 'data_plane_owner',
                'replay', 'strategy', 'feed', 'feed_receiver', 'session',
                'health', 'server_ns', 'trader_books', 'experiment_profile')}
            verify_state(state, args.profile)
            if before is not None:
                try:
                    receipt = verify_progress(before, state, args.profile)
                except ValueError as failure:
                    error = str(failure)
                    if before['session'] != state['session']:
                        before = state
                else:
                    print(json.dumps(receipt, ensure_ascii=False, indent=2))
                    return
            else:
                before = state
        except (ValueError, KeyError, TypeError, OSError) as failure:
            before, error = None, str(failure)
        time.sleep(0.5)
    raise SystemExit('book handoff failed: ' + error)


if __name__ == '__main__':
    main()
