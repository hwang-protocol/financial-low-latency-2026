CXX := g++-11
CXXFLAGS ?= -std=c++17 -O2 -g -Wall -Wextra -Wpedantic -pthread
CPPFLAGS ?= -Isrc

BUILD := build

.PHONY: all clean test tools tcpdirect dpdk

all: $(BUILD)/flle-exchange $(BUILD)/flle-trader $(BUILD)/flle-feed-receiver

tools: $(BUILD)/flle-itch-filter $(BUILD)/flle-book-checkpoint

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/flle-exchange: src/exchange.cpp src/common.hpp src/nasdaq_protocol.hpp src/itch_book.hpp src/market_config.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/exchange.cpp

$(BUILD)/flle-trader: src/trader.cpp src/posix_order_transport.cpp src/feed_ipc.hpp src/feed_handler.hpp src/order_transport.hpp src/common.hpp src/nasdaq_protocol.hpp src/itch_book.hpp src/order_queue.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/trader.cpp src/posix_order_transport.cpp

TCPDIRECT_TREE ?=
TCPDIRECT_BUILD ?= $(TCPDIRECT_TREE)/build/gnu_x86_64
TCPDIRECT_STATIC := $(TCPDIRECT_BUILD)/lib/libonload_zf_static.a

$(BUILD)/flle-trader-tcpdirect: src/trader.cpp src/tcpdirect_order_transport.cpp src/feed_ipc.hpp src/feed_handler.hpp src/order_transport.hpp src/common.hpp src/nasdaq_protocol.hpp src/itch_book.hpp src/order_queue.hpp | $(BUILD)
	test -n "$(TCPDIRECT_TREE)"
	test -s "$(TCPDIRECT_STATIC)"
	$(CXX) $(CPPFLAGS) -I$(TCPDIRECT_TREE)/src/include $(CXXFLAGS) -o $@ \
		src/trader.cpp src/tcpdirect_order_transport.cpp $(TCPDIRECT_STATIC) \
		-lm -lrt -ldl

tcpdirect: $(BUILD)/flle-trader-tcpdirect

FSTACK_TREE ?=
FSTACK_STATIC := $(FSTACK_TREE)/lib/libfstack.a

$(BUILD)/flle-trader-dpdk: src/dpdk_trader.cpp src/common.hpp src/nasdaq_protocol.hpp src/order_queue.hpp | $(BUILD)
	test -n "$(FSTACK_TREE)"
	test -s "$(FSTACK_STATIC)"
	$(CXX) $(CPPFLAGS) -I$(FSTACK_TREE)/lib $$(pkg-config --cflags libdpdk) \
		$(CXXFLAGS) -o $@ src/dpdk_trader.cpp $(FSTACK_STATIC) \
		$$(pkg-config --static --libs libdpdk) -lcrypto -lrt -ldl -lm

dpdk: $(BUILD)/flle-trader-dpdk

test: all $(BUILD)/flle-selftest
	$(BUILD)/flle-selftest
	python3 -m unittest discover -s tests -v

$(BUILD)/flle-selftest: src/selftest.cpp src/feed_handler.hpp src/common.hpp src/nasdaq_protocol.hpp src/itch_book.hpp src/order_queue.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/selftest.cpp

$(BUILD)/flle-itch-filter: src/itch_filter.cpp src/common.hpp src/nasdaq_protocol.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/itch_filter.cpp

$(BUILD)/flle-book-checkpoint: src/book_checkpoint.cpp src/common.hpp src/nasdaq_protocol.hpp src/itch_book.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/book_checkpoint.cpp

clean:
	rm -f $(BUILD)/flle-feed-receiver $(BUILD)/flle-exchange $(BUILD)/flle-trader $(BUILD)/flle-trader-tcpdirect $(BUILD)/flle-trader-dpdk $(BUILD)/flle-selftest $(BUILD)/flle-itch-filter $(BUILD)/flle-book-checkpoint

$(BUILD)/flle-feed-receiver: src/feed_receiver.cpp src/feed_ipc.hpp src/common.hpp src/market_config.hpp | $(BUILD)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ src/feed_receiver.cpp
