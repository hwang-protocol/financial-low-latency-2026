read -r -p '粘贴本次 evidence= 后面的目录：' OUT
test -s "$OUT/raw/MULTICAST.pcap"
tcpdump -nn -t -r "$OUT/raw/MULTICAST.pcap" -c 3
