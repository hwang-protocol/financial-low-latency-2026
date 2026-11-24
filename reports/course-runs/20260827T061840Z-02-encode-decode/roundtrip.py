import struct
# 32-byte Header 与 20-byte Tick Body 的格式串，前缀 ! 表示网络字节序。
header = struct.Struct("!HBBHHIQQI")
tick = struct.Struct("!H4sHIII")
# 课堂固定值：magic/version/type/reserved/header_len/body_len/session/correlation/sequence。
HEADER_VALUES = (0x464C, 1, 1, 0, 32, 20, 7, 701, 1)
# body magic / symbol / flags / price / quantity / tick sequence。
BODY_VALUES = (0x4D44, b"AAPL", 0, 1234501, 10, 1)
# 按布局表事先冻结的期望字节串：让 pack 结果对照外部向量，而不是自己证明自己。
EXPECTED_HEX = ("464c01010000002000000014000000000000000700000000000002bd00000001"
                "4d444141504c00000012d6450000000a00000001")

packet = header.pack(*HEADER_VALUES) + tick.pack(*BODY_VALUES)
print("packet_bytes=%d header_size=%d tick_size=%d hex_matches_frozen_vector=%s"
      % (len(packet), header.size, tick.size, packet.hex() == EXPECTED_HEX))
print("header_hex=%s" % packet[:32].hex())
print("body_hex=%s" % packet[32:].hex())

decoded_header = header.unpack(packet[:32])
decoded_body = tick.unpack(packet[32:])
print("decoded_session=%d decoded_correlation=%d decoded_sequence=%d"
      % (decoded_header[6], decoded_header[7], decoded_header[8]))
print("decoded_symbol=%s decoded_price=%d decoded_quantity=%d"
      % (decoded_body[1].decode(), decoded_body[3], decoded_body[4]))

# 同一段 wire bytes 分别按大端与小端解码：读错字节序就是另一个价格。
raw_price = packet[40:44]
print("offset_34_symbol=%s offset_40_price_hex=%s"
      % (packet[34:38].decode(), raw_price.hex()))
print("price_bigendian=%d price_littleendian=%d"
      % (struct.unpack("!I", raw_price)[0], struct.unpack("<I", raw_price)[0]))

# 冻结向量保证字节串本身正确，往返断言保证每个字段回到输入值。
assert packet.hex() == EXPECTED_HEX, "wire bytes differ from frozen vector"
assert decoded_header == HEADER_VALUES, "header roundtrip mismatch"
assert decoded_body == BODY_VALUES, "body roundtrip mismatch"
assert decoded_header[8] == decoded_body[5], "dual sequence contract broken"
print("verdict=FIELDS_MATCH")
