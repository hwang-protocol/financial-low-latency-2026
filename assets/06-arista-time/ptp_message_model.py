messages = [
    ("Sync", "master_to_slave_event"),
    ("Follow_Up", "master_to_slave_precise_time"),
    ("Delay_Req", "slave_to_master_event"),
    ("Delay_Resp", "master_to_slave_delay_reply"),
]
for name, role in messages:
    print("message=%s role=%s" % (name, role))
