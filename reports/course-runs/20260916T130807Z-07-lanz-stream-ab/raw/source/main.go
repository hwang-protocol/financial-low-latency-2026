// This adapter uses Arista's unmodified LANZ client and generated protobuf types.
// It formats decoded records; TCP framing and protobuf decoding belong to goarista.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/aristanetworks/goarista/lanz"
	pb "github.com/aristanetworks/goarista/lanz/proto"
)

const sdkVersion = "v0.0.0-20251201112602-a373d7c9f0d9"

type output struct {
	mu   sync.Mutex
	json bool
	w    io.Writer
}

func (o *output) emit(row map[string]any) {
	o.mu.Lock()
	defer o.mu.Unlock()
	if o.json {
		_ = json.NewEncoder(o.w).Encode(row)
		return
	}
	switch row["kind"] {
	case "connection":
		fmt.Fprintf(o.w, "[连接] connected=%v error=%v\n", row["connected"], row["error"])
	case "config":
		fmt.Fprintf(o.w, "[配置] 每个缓冲段=%v 字节\n", row["segment_size"])
	case "congestion":
		fmt.Fprintf(o.w, "[事件] 接口=%v 类型=%v TC=%v 队列=%v 段 时间=%v µs\n",
			row["intf_name"], row["entry_type"], row["traffic_class"], row["queue_size"], row["timestamp_us"])
	case "error":
		fmt.Fprintf(o.w, "[交换机错误] %v\n", row["message"])
	}
}

// WithConnector is the SDK's extension point. This wrapper only reports socket
// lifecycle to the webpage; it does not split or decode any incoming bytes.
type connection struct {
	mu   sync.Mutex
	conn net.Conn
	addr string
	out  *output
}

func (c *connection) Connect() error {
	conn, err := net.DialTimeout("tcp", c.addr, 5*time.Second)
	if err != nil {
		c.out.emit(map[string]any{"kind": "connection", "connected": false, "error": err.Error()})
		return err
	}
	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()
	c.out.emit(map[string]any{"kind": "connection", "connected": true, "error": ""})
	return nil
}

func (c *connection) Read(p []byte) (int, error) {
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()
	if conn == nil {
		return 0, io.EOF
	}
	return conn.Read(p)
}

func (c *connection) Close() error {
	c.mu.Lock()
	conn := c.conn
	c.conn = nil
	c.mu.Unlock()
	if conn == nil {
		return nil
	}
	err := conn.Close()
	c.out.emit(map[string]any{"kind": "connection", "connected": false, "error": "LANZ 连接已断开，等待重连"})
	return err
}

func present(record *pb.LanzRecord, out *output) bool {
	if config := record.GetConfigRecord(); config != nil {
		out.emit(map[string]any{
			"kind": "config", "timestamp_us": config.GetTimestamp(),
			"lanz_version": config.GetLanzVersion(), "num_of_ports": config.GetNumOfPorts(),
			"segment_size": config.GetSegmentSize(), "max_queue_size": config.GetMaxQueueSize(),
		})
	}
	if event := record.GetCongestionRecord(); event != nil {
		out.emit(map[string]any{
			"kind":         "congestion",
			"timestamp_us": event.GetTimestamp(),
			"intf_name":    event.GetIntfName(),
			"switch_id":    event.GetSwitchId(), "port_id": event.GetPortId(),
			"queue_size":       event.GetQueueSize(),
			"entry_type":       event.GetEntryType().String(),
			"traffic_class":    event.GetTrafficClass(),
			"time_of_max_qlen": event.GetTimeOfMaxQLen(),
			"tx_latency":       event.GetTxLatency(), "q_drop_count": event.GetQDropCount(),
		})
		return true
	}
	if problem := record.GetErrorRecord(); problem != nil {
		out.emit(map[string]any{"kind": "error", "message": problem.GetErrorMessage()})
	}
	return false
}

func receive(ctx context.Context, addr string, count int, out *output) {
	connector := &connection{addr: addr, out: out}
	client := lanz.New(lanz.WithAddr(addr), lanz.WithConnector(connector), lanz.WithBackoff(time.Second))
	events := make(chan *pb.LanzRecord)
	go client.Run(events)
	defer func() {
		client.Stop()
		// Drain any in-flight delivery so the SDK goroutine can finish cleanly.
		for range events {
		}
	}()
	seen := 0
	for {
		select {
		case <-ctx.Done():
			return
		case record, ok := <-events:
			if !ok {
				return
			}
			if present(record, out) {
				seen++
				if count > 0 && seen >= count {
					return
				}
			}
		}
	}
}

func main() {
	addr := flag.String("addr", "10.1.1.253:50001", "LANZ TCP address")
	asJSON := flag.Bool("json", false, "emit one JSON object per line for the webpage adapter")
	count := flag.Int("count", 0, "stop after this many congestion records; 0 keeps listening")
	version := flag.Bool("version", false, "show the pinned official client version")
	flag.Parse()
	if *version {
		fmt.Printf("flle-lanz-reader v1 · Arista goarista/lanz %s\n", sdkVersion)
		return
	}
	if *count < 0 {
		fmt.Fprintln(os.Stderr, "count must be nonnegative")
		os.Exit(2)
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	receive(ctx, *addr, *count, &output{json: *asJSON, w: os.Stdout})
}
