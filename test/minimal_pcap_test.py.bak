import pcap
sniffer = pcap.pcap(name=None, promisc=True, immediate=True, timeout_ms=50)
addr = lambda pkt, offset: '.'.join(str(pkt[i]) for i in range(offset, offset + 4))
for ts, pkt in sniffer:
    print('%d\tSRC %-16s\tDST %-16s' % (ts, addr(pkt, sniffer.dloff + 12), addr(pkt, sniffer.dloff + 16)))
