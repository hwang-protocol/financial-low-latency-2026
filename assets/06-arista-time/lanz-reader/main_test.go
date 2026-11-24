package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"net"
	"strings"
	"testing"
	"time"

	pb "github.com/aristanetworks/goarista/lanz/proto"
	"google.golang.org/protobuf/proto"
)

func frame(t *testing.T, message *pb.LanzRecord) []byte {
	t.Helper()
	payload, err := proto.Marshal(message)
	if err != nil {
		t.Fatal(err)
	}
	var size [10]byte
	n := binary.PutUvarint(size[:], uint64(len(payload)))
	return append(size[:n], payload...)
}

func event(kind pb.CongestionRecord_EntryType) *pb.LanzRecord {
	return &pb.LanzRecord{CongestionRecord: &pb.CongestionRecord{
		Timestamp: proto.Uint64(123456), IntfName: proto.String("Ethernet2"),
		SwitchId: proto.Uint32(0), PortId: proto.Uint32(2), QueueSize: proto.Uint32(64),
		EntryType: kind.Enum(), TrafficClass: proto.Uint32(1),
	}}
}

func TestOfficialClientFragmentationCoalescingReconnect(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	first := frame(t, event(pb.CongestionRecord_START))
	second := append(frame(t, event(pb.CongestionRecord_UPDATE)), frame(t, event(pb.CongestionRecord_END))...)
	serverDone := make(chan struct{})
	go func() {
		defer close(serverDone)
		conn, err := listener.Accept()
		if err != nil {
			return
		}
		// One record split across many writes, then a reconnect.
		for _, b := range first {
			_, _ = conn.Write([]byte{b})
		}
		conn.Close()
		conn, err = listener.Accept()
		if err != nil {
			return
		}
		// Two records coalesced in one TCP write.
		_, _ = conn.Write(second)
		conn.Close()
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	var buf bytes.Buffer
	receive(ctx, listener.Addr().String(), 3, &output{json: true, w: &buf})
	if ctx.Err() != nil {
		t.Fatal("reader failed to finish", buf.String())
	}
	<-serverDone
	var types []string
	connected := 0
	for _, line := range strings.Split(strings.TrimSpace(buf.String()), "\n") {
		var row map[string]any
		if err := json.Unmarshal([]byte(line), &row); err != nil {
			t.Fatal(err, line)
		}
		if row["kind"] == "connection" && row["connected"] == true {
			connected++
		}
		if row["kind"] == "congestion" {
			types = append(types, row["entry_type"].(string))
			if row["intf_name"] != "Ethernet2" || row["queue_size"] != float64(64) || row["traffic_class"] != float64(1) {
				t.Fatal(row)
			}
		}
	}
	if strings.Join(types, ",") != "START,UPDATE,END" || connected != 2 {
		t.Fatal(types, connected, buf.String())
	}
}

func TestOfficialConfigAndTerminalOutput(t *testing.T) {
	var buf bytes.Buffer
	out := &output{w: &buf}
	present(&pb.LanzRecord{ConfigRecord: &pb.ConfigRecord{SegmentSize: proto.Uint32(480)}}, out)
	present(event(pb.CongestionRecord_END), out)
	if !strings.Contains(buf.String(), "每个缓冲段=480 字节") || !strings.Contains(buf.String(), "接口=Ethernet2 类型=END TC=1 队列=64 段") {
		t.Fatal(buf.String())
	}
}

func Test7150TimestampScale(t *testing.T) {
	var buf bytes.Buffer
	record := event(pb.CongestionRecord_START)
	record.CongestionRecord.Timestamp = proto.Uint64(178956311872900)
	present(record, &output{json: true, w: &buf})
	var row map[string]any
	if err := json.Unmarshal(buf.Bytes(), &row); err != nil {
		t.Fatal(err)
	}
	if row["timestamp_raw"] != float64(178956311872900) || row["timestamp_tick_us"] != float64(10) || row["timestamp_us"] != float64(1789563118729000) {
		t.Fatal(row)
	}
	if eventTime(178956311872900) != "2026-09-16 12:51:58.729000 UTC" {
		t.Fatal(eventTime(178956311872900))
	}
	buf.Reset()
	present(&pb.LanzRecord{ConfigRecord: &pb.ConfigRecord{Timestamp: proto.Uint64(178956309674099)}}, &output{json: true, w: &buf})
	if err := json.Unmarshal(buf.Bytes(), &row); err != nil {
		t.Fatal(err)
	}
	if row["timestamp_us"] != float64(1789563096740990) {
		t.Fatal(row)
	}
}
